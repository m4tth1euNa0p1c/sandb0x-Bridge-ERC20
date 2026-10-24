// SPDX-License-Identifier: MIT
pragma solidity 0.8.30;

import {AccessControl} from "@openzeppelin/contracts/access/AccessControl.sol";
import {Pausable} from "@openzeppelin/contracts/utils/Pausable.sol";
import {ReentrancyGuard} from "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import {BridgeToken} from "./BridgeToken.sol";

/// @notice Authorized-relayer burn/mint demonstrator. No cross-chain proof is verified.
/// @dev An executor can fabricate source observations within these limits. It is trusted.
contract Bridge is AccessControl, Pausable, ReentrancyGuard {
    bytes32 public constant PROTOCOL_DOMAIN = keccak256("T3L4N_BRIDGE_BURN_MINT");
    uint256 public constant PROTOCOL_VERSION = 1;
    bytes32 public constant EXECUTOR_ROLE = keccak256("EXECUTOR_ROLE");
    bytes32 public constant PAUSER_ROLE = keccak256("PAUSER_ROLE");

    BridgeToken public immutable token;
    uint256 public immutable localChainId;
    uint256 public immutable maxTransfer;
    uint256 public immutable epochMintCap;
    uint256 public immutable epochSeconds;
    uint256 public nextNonce; // First source transfer is nonce zero.

    struct Pair {
        address remoteBridge;
        address remoteToken;
    }

    mapping(uint256 remoteChainId => Pair) public pairs;
    mapping(bytes32 transferId => bool) public processed;
    mapping(uint256 epoch => uint256 amount) public mintedInEpoch;

    error InvalidAddress();
    error InvalidLimits();
    error UnsupportedToken();
    error UnsupportedDecimals(uint8 decimals);
    error InvalidChain(uint256 chainId);
    error NetworkChanged(uint256 observedChainId, uint256 expectedChainId);
    error PairAlreadyConfigured(uint256 chainId);
    error PairNotConfigured(uint256 chainId);
    error PairMismatch();
    error InvalidAmount(uint256 amount);
    error TransferAlreadyProcessed(bytes32 transferId);
    error EpochMintCapExceeded(uint256 epoch, uint256 attemptedTotal);

    event PairConfigured(uint256 indexed remoteChainId, address remoteBridge, address remoteToken);
    event TransferInitiated(
        bytes32 indexed transferId,
        uint256 indexed destinationChainId,
        address indexed sender,
        address recipient,
        address sourceToken,
        address destinationToken,
        address destinationBridge,
        uint256 nonce,
        uint256 amount
    );
    event TransferCompleted(bytes32 indexed transferId, address indexed recipient, uint256 amount);

    constructor(
        address token_,
        address admin,
        address pauser,
        address executor,
        uint256 maxTransfer_,
        uint256 epochMintCap_,
        uint256 epochSeconds_
    ) {
        if (token_ == address(0) || admin == address(0) || pauser == address(0) || executor == address(0)) {
            revert InvalidAddress();
        }
        if (maxTransfer_ == 0 || epochMintCap_ < maxTransfer_ || epochSeconds_ == 0) revert InvalidLimits();
        // Only this exact, non-upgradeable dedicated token implementation is supported locally.
        // Remote token identity is an operator check: this chain cannot inspect remote bytecode.
        if (token_.codehash != keccak256(type(BridgeToken).runtimeCode)) revert UnsupportedToken();
        token = BridgeToken(token_);
        localChainId = block.chainid;
        if (token.decimals() != 18) revert UnsupportedDecimals(token.decimals());
        maxTransfer = maxTransfer_;
        epochMintCap = epochMintCap_;
        epochSeconds = epochSeconds_;
        _grantRole(DEFAULT_ADMIN_ROLE, admin);
        _grantRole(PAUSER_ROLE, pauser);
        _grantRole(EXECUTOR_ROLE, executor);
    }

    /// @notice Pair configuration is write-once to keep previously burned transfers resolvable.
    /// @dev Operator must separately verify remote runtime code and permissions on that network.
    function configurePair(uint256 remoteChainId, address remoteBridge, address remoteToken, uint8 remoteDecimals)
        external
        onlyRole(DEFAULT_ADMIN_ROLE)
    {
        if (remoteChainId == 0 || remoteChainId == block.chainid) revert InvalidChain(remoteChainId);
        if (remoteBridge == address(0) || remoteToken == address(0)) revert InvalidAddress();
        if (remoteDecimals != 18) revert UnsupportedDecimals(remoteDecimals);
        if (pairs[remoteChainId].remoteBridge != address(0)) revert PairAlreadyConfigured(remoteChainId);
        pairs[remoteChainId] = Pair(remoteBridge, remoteToken);
        emit PairConfigured(remoteChainId, remoteBridge, remoteToken);
    }

    function pause() external onlyRole(PAUSER_ROLE) {
        _pause();
    }

    function unpause() external onlyRole(DEFAULT_ADMIN_ROLE) {
        _unpause();
    }

    function requestTransfer(uint256 destinationChainId, address recipient, uint256 amount)
        external
        whenNotPaused
        nonReentrant
        returns (bytes32 transferId)
    {
        Pair memory pair = _pair(destinationChainId);
        _validateTransfer(recipient, amount);
        uint256 nonce = nextNonce++;
        transferId = _transferId(
            block.chainid,
            address(this),
            destinationChainId,
            pair.remoteBridge,
            address(token),
            pair.remoteToken,
            nonce,
            amount,
            recipient
        );
        token.burnFrom(_msgSender(), amount);
        emit TransferInitiated(
            transferId,
            destinationChainId,
            _msgSender(),
            recipient,
            address(token),
            pair.remoteToken,
            pair.remoteBridge,
            nonce,
            amount
        );
    }

    function completeTransfer(
        uint256 sourceChainId,
        address sourceBridge,
        address sourceToken,
        uint256 nonce,
        uint256 amount,
        address recipient
    ) external onlyRole(EXECUTOR_ROLE) whenNotPaused nonReentrant {
        Pair memory pair = _pair(sourceChainId);
        if (pair.remoteBridge != sourceBridge || pair.remoteToken != sourceToken) revert PairMismatch();
        _validateTransfer(recipient, amount);
        bytes32 transferId = _transferId(
            sourceChainId,
            sourceBridge,
            block.chainid,
            address(this),
            sourceToken,
            address(token),
            nonce,
            amount,
            recipient
        );
        if (processed[transferId]) revert TransferAlreadyProcessed(transferId);
        uint256 epoch = block.timestamp / epochSeconds;
        uint256 total = mintedInEpoch[epoch] + amount;
        if (total > epochMintCap) revert EpochMintCapExceeded(epoch, total);
        // Both effects roll back if token.mint reverts.
        processed[transferId] = true;
        mintedInEpoch[epoch] = total;
        token.mint(recipient, amount);
        emit TransferCompleted(transferId, recipient, amount);
    }

    /// @notice Pure off-chain coordination helper; encoding is the protocol v1 fixed domain.
    function computeTransferId(
        uint256 sourceChainId,
        address sourceBridge,
        uint256 destinationChainId,
        address destinationBridge,
        address sourceToken,
        address destinationToken,
        uint256 nonce,
        uint256 amount,
        address recipient
    ) external pure returns (bytes32) {
        return _transferId(
            sourceChainId,
            sourceBridge,
            destinationChainId,
            destinationBridge,
            sourceToken,
            destinationToken,
            nonce,
            amount,
            recipient
        );
    }

    function _pair(uint256 remoteChainId) private view returns (Pair memory pair) {
        if (block.chainid != localChainId) revert NetworkChanged(block.chainid, localChainId);
        if (remoteChainId == 0 || remoteChainId == block.chainid) revert InvalidChain(remoteChainId);
        pair = pairs[remoteChainId];
        if (pair.remoteBridge == address(0)) revert PairNotConfigured(remoteChainId);
    }

    function _validateTransfer(address recipient, uint256 amount) private view {
        if (recipient == address(0)) revert InvalidAddress();
        if (amount == 0 || amount > maxTransfer) revert InvalidAmount(amount);
    }

    function _transferId(
        uint256 sourceChainId,
        address sourceBridge,
        uint256 destinationChainId,
        address destinationBridge,
        address sourceToken,
        address destinationToken,
        uint256 nonce,
        uint256 amount,
        address recipient
    ) private pure returns (bytes32) {
        return keccak256(
            abi.encode(
                PROTOCOL_DOMAIN,
                uint256(1),
                sourceChainId,
                sourceBridge,
                destinationChainId,
                destinationBridge,
                sourceToken,
                destinationToken,
                nonce,
                amount,
                recipient
            )
        );
    }
}
