// SPDX-License-Identifier: MIT
pragma solidity 0.8.30;

import {Bridge} from "../src/Bridge.sol";
import {BridgeToken} from "../src/BridgeToken.sol";
import {TestSupport, Vm} from "./TestSupport.sol";

contract BridgeTest is TestSupport {
    uint256 internal constant CHAIN_A = 31337;
    uint256 internal constant CHAIN_B = 31338;
    uint256 internal constant INITIAL = 1_000_000 ether;
    uint256 internal constant MAX = 1_000 ether;
    uint256 internal constant CAP = 2_000 ether;
    uint256 internal constant EPOCH = 3600;
    address internal constant ADMIN = address(0xA11);
    address internal constant PAUSER = address(0xBA0);
    address internal constant EXECUTOR = address(0xE1);
    address internal constant ALICE = address(0xA1);
    address internal constant BOB = address(0xB0B);
    bytes32 internal constant BRIDGE_ROLE = keccak256("BRIDGE_ROLE");
    bytes32 internal constant EXECUTOR_ROLE = keccak256("EXECUTOR_ROLE");
    bytes32 internal constant PAUSER_ROLE = keccak256("PAUSER_ROLE");
    BridgeToken internal tokenA;
    BridgeToken internal tokenB;
    Bridge internal bridgeA;
    Bridge internal bridgeB;

    function setUp() public {
        vm.chainId(CHAIN_A);
        vm.warp(1_700_000_000);
        tokenA = new BridgeToken("Test A", "TSTA", ADMIN, ALICE, INITIAL);
        bridgeA = new Bridge(address(tokenA), ADMIN, PAUSER, EXECUTOR, MAX, CAP, EPOCH);
        vm.chainId(CHAIN_B);
        tokenB = new BridgeToken("Test B", "TSTB", ADMIN, ALICE, 0);
        bridgeB = new Bridge(address(tokenB), ADMIN, PAUSER, EXECUTOR, MAX, CAP, EPOCH);
        vm.startPrank(ADMIN);
        tokenA.grantRole(BRIDGE_ROLE, address(bridgeA));
        tokenB.grantRole(BRIDGE_ROLE, address(bridgeB));
        bridgeB.configurePair(CHAIN_A, address(bridgeA), address(tokenA), 18);
        vm.chainId(CHAIN_A);
        bridgeA.configurePair(CHAIN_B, address(bridgeB), address(tokenB), 18);
        vm.stopPrank();
        vm.prank(ALICE);
        tokenA.approve(address(bridgeA), type(uint256).max);
    }

    function _request(uint256 amount, address recipient) internal returns (bytes32) {
        vm.chainId(CHAIN_A);
        vm.prank(ALICE);
        return bridgeA.requestTransfer(CHAIN_B, recipient, amount);
    }

    function _complete(uint256 nonce, uint256 amount, address recipient) internal {
        vm.chainId(CHAIN_B);
        vm.prank(EXECUTOR);
        bridgeB.completeTransfer(CHAIN_A, address(bridgeA), address(tokenA), nonce, amount, recipient);
    }

    function testRoundTripConservesSupplyAndRecipientBalances() public {
        bytes32 first = _request(123 ether, BOB);
        assertEq(tokenA.balanceOf(ALICE), INITIAL - 123 ether, "source burn");
        assertEq(tokenA.totalSupply() + tokenB.totalSupply() + 123 ether, INITIAL, "in-transit conservation");
        _complete(0, 123 ether, BOB);
        assertTrue(bridgeB.processed(first), "destination marks source id");
        assertEq(tokenB.balanceOf(BOB), 123 ether, "recipient credited");
        assertEq(tokenB.balanceOf(ALICE), 0, "sender not credited accidentally");
        assertEq(tokenA.totalSupply() + tokenB.totalSupply(), INITIAL, "forward supply");
        vm.startPrank(BOB);
        tokenB.approve(address(bridgeB), 123 ether);
        bytes32 back = bridgeB.requestTransfer(CHAIN_A, ALICE, 123 ether);
        vm.stopPrank();
        assertTrue(back != first, "directions have distinct ids");
        vm.chainId(CHAIN_A);
        vm.prank(EXECUTOR);
        bridgeA.completeTransfer(CHAIN_B, address(bridgeB), address(tokenB), 0, 123 ether, ALICE);
        assertTrue(bridgeA.processed(back), "return id processed");
        assertEq(tokenA.balanceOf(ALICE), INITIAL, "round trip balance");
        assertEq(tokenB.totalSupply(), 0, "return source burned");
        assertEq(tokenA.totalSupply(), INITIAL, "round trip supply");
        assertEq(tokenA.decimals(), 18, "decimals A");
        assertEq(tokenB.decimals(), 18, "decimals B");
    }

    function testEventContainsExactTransferIntentAndNonceZero() public {
        vm.recordLogs();
        bytes32 id = _request(5 ether, BOB);
        Vm.Log[] memory logs = vm.getRecordedLogs();
        uint256 matches;
        for (uint256 i; i < logs.length; ++i) {
            if (logs[i].emitter != address(bridgeA)) continue;
            ++matches;
            assertEq(
                logs[i].topics[0],
                keccak256("TransferInitiated(bytes32,uint256,address,address,address,address,address,uint256,uint256)"),
                "event signature"
            );
            assertEq(logs[i].topics[1], id, "indexed id");
            assertEq(logs[i].topics[2], bytes32(CHAIN_B), "indexed chain");
            assertEq(logs[i].topics[3], bytes32(uint256(uint160(ALICE))), "indexed sender");
            (
                address recipient,
                address sourceToken,
                address destinationToken,
                address destinationBridge,
                uint256 nonce,
                uint256 amount
            ) = abi.decode(logs[i].data, (address, address, address, address, uint256, uint256));
            assertEq(recipient, BOB, "event recipient");
            assertEq(sourceToken, address(tokenA), "event source token");
            assertEq(destinationToken, address(tokenB), "event destination token");
            assertEq(destinationBridge, address(bridgeB), "event destination bridge");
            assertEq(nonce, 0, "first nonce is zero");
            assertEq(amount, 5 ether, "integer amount");
        }
        assertEq(matches, 1, "exactly one initiated event");
        assertEq(bridgeA.nextNonce(), 1, "next nonce increments once");
    }

    function testDuplicateObservationCannotMintTwice() public {
        bytes32 id = _request(1 ether, BOB);
        _complete(0, 1 ether, BOB);
        vm.expectRevert(abi.encodeWithSelector(Bridge.TransferAlreadyProcessed.selector, id));
        _complete(0, 1 ether, BOB);
        assertEq(tokenB.totalSupply(), 1 ether, "duplicate no supply effect");
    }

    function testUnauthorizedExecutorAndTokenMinterAreRejected() public {
        _request(1 ether, BOB);
        vm.chainId(CHAIN_B);
        vm.prank(ALICE);
        vm.expectRevert();
        bridgeB.completeTransfer(CHAIN_A, address(bridgeA), address(tokenA), 0, 1 ether, BOB);
        vm.prank(ALICE);
        vm.expectRevert();
        tokenB.mint(ALICE, 1 ether);
        vm.prank(ALICE);
        vm.expectRevert();
        tokenA.burnFrom(ALICE, 1 ether);
        assertEq(tokenB.totalSupply(), 0, "no unauthorized mint");
    }

    function testAllowanceIsRequiredAndFailureKeepsNonceAndSupply() public {
        vm.prank(ALICE);
        tokenA.approve(address(bridgeA), 0);
        vm.prank(ALICE);
        vm.expectRevert();
        bridgeA.requestTransfer(CHAIN_B, BOB, 1 ether);
        assertEq(bridgeA.nextNonce(), 0, "failed burn nonce rollback");
        assertEq(tokenA.totalSupply(), INITIAL, "failed burn supply rollback");
    }

    function testFiniteAllowanceIsConsumedExactly() public {
        vm.prank(ALICE);
        tokenA.approve(address(bridgeA), 4 ether);
        _request(3 ether, BOB);
        assertEq(tokenA.allowance(ALICE, address(bridgeA)), 1 ether, "allowance spend");
        assertEq(tokenA.balanceOf(ALICE), INITIAL - 3 ether, "same amount burned");
    }

    function testProcessedAndEpochQuotaRollbackWhenMintRoleMissing() public {
        bytes32 id = _request(1 ether, BOB);
        vm.startPrank(ADMIN);
        tokenB.revokeRole(BRIDGE_ROLE, address(bridgeB));
        vm.stopPrank();
        vm.expectRevert();
        _complete(0, 1 ether, BOB);
        assertTrue(!bridgeB.processed(id), "processed rolls back");
        assertEq(bridgeB.mintedInEpoch(block.timestamp / EPOCH), 0, "quota rolls back");
        assertEq(tokenB.totalSupply(), 0, "supply unchanged");
        vm.prank(ADMIN);
        tokenB.grantRole(BRIDGE_ROLE, address(bridgeB));
        _complete(0, 1 ether, BOB);
        assertTrue(bridgeB.processed(id), "retry after explicit permission repair");
    }

    function testWrongSourceBridgeTokenAndChainCannotReplay() public {
        _request(1 ether, BOB);
        vm.chainId(CHAIN_B);
        vm.startPrank(EXECUTOR);
        vm.expectRevert(Bridge.PairMismatch.selector);
        bridgeB.completeTransfer(CHAIN_A, address(0x1234), address(tokenA), 0, 1 ether, BOB);
        vm.expectRevert(Bridge.PairMismatch.selector);
        bridgeB.completeTransfer(CHAIN_A, address(bridgeA), address(0x1234), 0, 1 ether, BOB);
        vm.expectRevert(abi.encodeWithSelector(Bridge.PairNotConfigured.selector, CHAIN_A + 10));
        bridgeB.completeTransfer(CHAIN_A + 10, address(bridgeA), address(tokenA), 0, 1 ether, BOB);
        vm.stopPrank();
        assertEq(tokenB.totalSupply(), 0, "context replay no mint");
    }

    function testChangedChainIdentityIsRejected() public {
        vm.chainId(1);
        vm.prank(ALICE);
        vm.expectRevert(abi.encodeWithSelector(Bridge.NetworkChanged.selector, 1, CHAIN_A));
        bridgeA.requestTransfer(CHAIN_B, BOB, 1 ether);
    }

    function testPauseStopsBurnAndMintAdminResumes() public {
        bytes32 id = _request(1 ether, BOB);
        vm.prank(PAUSER);
        bridgeA.pause();
        vm.prank(ALICE);
        vm.expectRevert();
        bridgeA.requestTransfer(CHAIN_B, BOB, 1 ether);
        vm.chainId(CHAIN_B);
        vm.prank(PAUSER);
        bridgeB.pause();
        vm.expectRevert();
        _complete(0, 1 ether, BOB);
        vm.prank(PAUSER);
        vm.expectRevert();
        bridgeB.unpause();
        vm.prank(EXECUTOR);
        vm.expectRevert();
        bridgeB.unpause();
        vm.prank(ADMIN);
        bridgeB.unpause();
        _complete(0, 1 ether, BOB);
        assertTrue(bridgeB.processed(id), "backlog can resume");
        vm.chainId(CHAIN_A);
        vm.prank(ADMIN);
        bridgeA.unpause();
        _request(1 ether, BOB);
        assertEq(bridgeA.nextNonce(), 2, "paused request consumed no nonce");
    }

    function testExecutorCannotGrantRoleAndAdminCanRevokeIt() public {
        vm.prank(EXECUTOR);
        vm.expectRevert();
        bridgeA.grantRole(bytes32(0), EXECUTOR);
        vm.prank(ADMIN);
        bridgeB.revokeRole(EXECUTOR_ROLE, EXECUTOR);
        vm.expectRevert();
        _complete(0, 1 ether, BOB);
        vm.prank(ADMIN);
        bridgeB.grantRole(EXECUTOR_ROLE, EXECUTOR);
        _complete(0, 1 ether, BOB);
        assertEq(tokenB.balanceOf(BOB), 1 ether, "admin grant restores executor");
    }

    function testTrustedExecutorCanFabricateMintWithoutSourceBurn() public {
        // Deliberately records the trust limitation instead of pretending to verify a source proof.
        _complete(987, 1 ether, BOB);
        assertEq(tokenA.totalSupply(), INITIAL, "no burn was made");
        assertEq(tokenB.totalSupply(), 1 ether, "authorized fabricated mint is possible");
    }

    function testInvalidAmountsAndRecipientsAreRejected() public {
        vm.startPrank(ALICE);
        vm.expectRevert(abi.encodeWithSelector(Bridge.InvalidAmount.selector, 0));
        bridgeA.requestTransfer(CHAIN_B, BOB, 0);
        vm.expectRevert(abi.encodeWithSelector(Bridge.InvalidAmount.selector, MAX + 1));
        bridgeA.requestTransfer(CHAIN_B, BOB, MAX + 1);
        vm.expectRevert(Bridge.InvalidAddress.selector);
        bridgeA.requestTransfer(CHAIN_B, address(0), 1);
        vm.stopPrank();
        vm.expectRevert(Bridge.InvalidAddress.selector);
        _complete(0, 1, address(0));
        assertEq(tokenA.totalSupply(), INITIAL, "invalid requests no burn");
        assertEq(bridgeA.nextNonce(), 0, "invalid requests no nonce");
    }

    function testEpochCapBoundaryAndReset() public {
        _complete(0, MAX, BOB);
        _complete(1, MAX, BOB);
        vm.expectRevert(abi.encodeWithSelector(Bridge.EpochMintCapExceeded.selector, block.timestamp / EPOCH, CAP + 1));
        _complete(2, 1, BOB);
        assertEq(tokenB.totalSupply(), CAP, "cap exact boundary");
        vm.warp((block.timestamp / EPOCH + 1) * EPOCH);
        _complete(2, 1, BOB);
        assertEq(tokenB.totalSupply(), CAP + 1, "new epoch permits pending intent");
    }

    function testConfigurationRejectsUnknownTokenAndDecimalsAndRemapping() public {
        vm.expectRevert(Bridge.UnsupportedToken.selector);
        new Bridge(address(this), ADMIN, PAUSER, EXECUTOR, MAX, CAP, EPOCH);
        vm.startPrank(ADMIN);
        vm.expectRevert(abi.encodeWithSelector(Bridge.UnsupportedDecimals.selector, uint8(6)));
        bridgeA.configurePair(CHAIN_B + 10, address(bridgeB), address(tokenB), 6);
        vm.expectRevert(abi.encodeWithSelector(Bridge.PairAlreadyConfigured.selector, CHAIN_B));
        bridgeA.configurePair(CHAIN_B, address(0x1234), address(tokenB), 18);
        vm.expectRevert(abi.encodeWithSelector(Bridge.InvalidChain.selector, CHAIN_A));
        bridgeA.configurePair(CHAIN_A, address(bridgeB), address(tokenB), 18);
        vm.stopPrank();
    }

    function testRolesAreSeparateAndConfigurationRequiresAdmin() public {
        assertTrue(bridgeA.hasRole(bytes32(0), ADMIN), "admin is assigned");
        assertTrue(!bridgeA.hasRole(EXECUTOR_ROLE, ADMIN), "admin not automatically executor");
        assertTrue(!bridgeA.hasRole(PAUSER_ROLE, ADMIN), "admin not automatically pauser");
        assertTrue(!bridgeA.hasRole(bytes32(0), EXECUTOR), "executor not admin");
        assertEq(bridgeA.getRoleAdmin(EXECUTOR_ROLE), bytes32(0), "admin manages executor");
        assertEq(bridgeA.getRoleAdmin(PAUSER_ROLE), bytes32(0), "admin manages pauser");
        vm.prank(EXECUTOR);
        vm.expectRevert();
        bridgeA.configurePair(100, address(1), address(2), 18);
        vm.prank(EXECUTOR);
        vm.expectRevert();
        bridgeA.pause();
        vm.prank(ADMIN);
        vm.expectRevert();
        bridgeA.pause();
    }

    function testRevokedPauserLosesPowerAndAdminCanAssignReplacement() public {
        vm.prank(ADMIN);
        bridgeA.revokeRole(PAUSER_ROLE, PAUSER);
        vm.prank(PAUSER);
        vm.expectRevert();
        bridgeA.pause();
        vm.prank(ADMIN);
        bridgeA.grantRole(PAUSER_ROLE, ALICE);
        vm.prank(ALICE);
        bridgeA.pause();
        assertTrue(bridgeA.paused(), "replacement pauser effective");
    }

    function testBurnFailureEmitsNoBridgeEventAndConsumesNoNonce() public {
        vm.prank(ADMIN);
        tokenA.revokeRole(BRIDGE_ROLE, address(bridgeA));
        vm.recordLogs();
        vm.expectRevert();
        _request(1 ether, BOB);
        Vm.Log[] memory logs = vm.getRecordedLogs();
        for (uint256 i; i < logs.length; ++i) {
            assertTrue(logs[i].emitter != address(bridgeA), "no initiated event on failed burn");
        }
        assertEq(bridgeA.nextNonce(), 0, "nonce rollback on failed burn");
        assertEq(tokenA.totalSupply(), INITIAL, "source supply unchanged");
    }

    function testInsufficientBalanceRollsBackAllowanceSpend() public {
        vm.startPrank(BOB);
        tokenA.approve(address(bridgeA), 1 ether);
        vm.expectRevert();
        bridgeA.requestTransfer(CHAIN_B, BOB, 1 ether);
        vm.stopPrank();
        assertEq(tokenA.allowance(BOB, address(bridgeA)), 1 ether, "failed burn restores allowance");
        assertEq(bridgeA.nextNonce(), 0, "failed balance nonce rollback");
    }

    function testInvalidConstructorAddressesAndLimitsRejected() public {
        vm.expectRevert(BridgeToken.InvalidAddress.selector);
        new BridgeToken("Invalid", "INV", address(0), ALICE, 0);
        vm.expectRevert(BridgeToken.InvalidAddress.selector);
        new BridgeToken("Invalid", "INV", ADMIN, address(0), 0);
        vm.expectRevert(Bridge.InvalidAddress.selector);
        new Bridge(address(tokenA), ADMIN, PAUSER, address(0), MAX, CAP, EPOCH);
        vm.expectRevert(Bridge.InvalidLimits.selector);
        new Bridge(address(tokenA), ADMIN, PAUSER, EXECUTOR, 0, CAP, EPOCH);
        vm.expectRevert(Bridge.InvalidLimits.selector);
        new Bridge(address(tokenA), ADMIN, PAUSER, EXECUTOR, MAX, MAX - 1, EPOCH);
        vm.expectRevert(Bridge.InvalidLimits.selector);
        new Bridge(address(tokenA), ADMIN, PAUSER, EXECUTOR, MAX, CAP, 0);
    }

    function testFuzzRoundTripPreservesIntegerUnits(uint96 rawAmount, address recipient) public {
        uint256 amount = uint256(rawAmount) % MAX + 1;
        if (recipient == address(0)) recipient = BOB;
        _request(amount, recipient);
        _complete(0, amount, recipient);
        assertEq(tokenB.balanceOf(recipient), amount, "exact destination integer amount");
        vm.startPrank(recipient);
        tokenB.approve(address(bridgeB), amount);
        bridgeB.requestTransfer(CHAIN_A, ALICE, amount);
        vm.stopPrank();
        vm.chainId(CHAIN_A);
        vm.prank(EXECUTOR);
        bridgeA.completeTransfer(CHAIN_B, address(bridgeB), address(tokenB), 0, amount, ALICE);
        assertEq(tokenA.balanceOf(ALICE), INITIAL, "fuzz round trip source balance");
        assertEq(tokenB.totalSupply(), 0, "fuzz round trip destination supply");
    }

    function testFuzzAboveTransferLimitHasNoEffect(uint256 excess) public {
        uint256 amount = MAX + 1 + (excess % (type(uint256).max - MAX));
        vm.expectRevert(abi.encodeWithSelector(Bridge.InvalidAmount.selector, amount));
        _request(amount, BOB);
        assertEq(tokenA.totalSupply(), INITIAL, "oversize request no burn");
        assertEq(bridgeA.nextNonce(), 0, "oversize request no nonce");
    }
}
