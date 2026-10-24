// SPDX-License-Identifier: MIT
pragma solidity 0.8.30;

import {Bridge} from "../src/Bridge.sol";
import {BridgeToken} from "../src/BridgeToken.sol";
import {TestSupport} from "./TestSupport.sol";

contract BridgeHandler is TestSupport {
    uint256 internal constant CHAIN_A = 31337;
    uint256 internal constant CHAIN_B = 31338;
    uint256 internal constant MAX = 1_000 ether;
    address internal constant ADMIN = address(0xA11);
    address internal constant PAUSER = address(0xBA0);
    address internal constant EXECUTOR = address(0xE1);
    address internal constant ALICE = address(0xA1);
    address internal constant BOB = address(0xB0B);
    BridgeToken public immutable tokenA;
    BridgeToken public immutable tokenB;
    Bridge public immutable bridgeA;
    Bridge public immutable bridgeB;

    struct Intent {
        bool fromA;
        bytes32 id;
        uint256 nonce;
        uint256 amount;
        bool completed;
    }

    Intent[] private intents;
    uint256 public inTransit;
    uint256 public sourceBurned;
    uint256 public destinationMinted;
    uint256 public requests;
    uint256 public completions;
    uint256 public duplicateChecks;
    uint256 public pauseChecks;
    uint256 public revokedRoleChecks;

    constructor(BridgeToken a, BridgeToken b, Bridge ba, Bridge bb) {
        tokenA = a;
        tokenB = b;
        bridgeA = ba;
        bridgeB = bb;
    }

    function sendA(uint96 raw) external {
        _request(true, raw);
    }

    function sendB(uint96 raw) external {
        _request(false, raw);
    }

    function _request(bool fromA, uint96 raw) private {
        vm.chainId(fromA ? CHAIN_A : CHAIN_B);
        Bridge source = fromA ? bridgeA : bridgeB;
        BridgeToken sourceToken = fromA ? tokenA : tokenB;
        address sender = fromA ? ALICE : BOB;
        uint256 balance = sourceToken.balanceOf(sender);
        if (balance == 0) return;
        uint256 bound = balance < MAX ? balance : MAX;
        uint256 amount = uint256(raw) % bound + 1;
        uint256 nonce = source.nextNonce();
        vm.prank(sender);
        bytes32 id = source.requestTransfer(fromA ? CHAIN_B : CHAIN_A, fromA ? BOB : ALICE, amount);
        intents.push(Intent(fromA, id, nonce, amount, false));
        inTransit += amount;
        sourceBurned += amount;
        ++requests;
    }

    function deliver(uint256 index) external {
        if (intents.length == 0) return;
        Intent storage intent = intents[index % intents.length];
        if (intent.completed) return;
        Bridge destination = intent.fromA ? bridgeB : bridgeA;
        BridgeToken destinationToken = intent.fromA ? tokenB : tokenA;
        vm.chainId(intent.fromA ? CHAIN_B : CHAIN_A);
        uint256 supplyBefore = destinationToken.totalSupply();
        vm.prank(EXECUTOR);
        destination.completeTransfer(
            intent.fromA ? CHAIN_A : CHAIN_B,
            address(intent.fromA ? bridgeA : bridgeB),
            address(intent.fromA ? tokenA : tokenB),
            intent.nonce,
            intent.amount,
            intent.fromA ? BOB : ALICE
        );
        assertEq(destinationToken.totalSupply() - supplyBefore, intent.amount, "mint amount matches independent intent");
        assertTrue(destination.processed(intent.id), "source id processed on destination");
        intent.completed = true;
        inTransit -= intent.amount;
        destinationMinted += intent.amount;
        ++completions;
    }

    function duplicate(uint256 index) external {
        if (intents.length == 0) return;
        Intent memory intent = intents[index % intents.length];
        if (!intent.completed) return;
        Bridge destination = intent.fromA ? bridgeB : bridgeA;
        BridgeToken destinationToken = intent.fromA ? tokenB : tokenA;
        vm.chainId(intent.fromA ? CHAIN_B : CHAIN_A);
        uint256 beforeSupply = destinationToken.totalSupply();
        vm.prank(EXECUTOR);
        (bool ok,) = address(destination).call(
            abi.encodeCall(
                Bridge.completeTransfer,
                (
                    intent.fromA ? CHAIN_A : CHAIN_B,
                    address(intent.fromA ? bridgeA : bridgeB),
                    address(intent.fromA ? tokenA : tokenB),
                    intent.nonce,
                    intent.amount,
                    intent.fromA ? BOB : ALICE
                )
            )
        );
        assertTrue(!ok, "duplicate rejected");
        assertEq(destinationToken.totalSupply(), beforeSupply, "duplicate did not mint");
        ++duplicateChecks;
    }

    function pausedRequest(bool fromA) external {
        vm.chainId(fromA ? CHAIN_A : CHAIN_B);
        Bridge source = fromA ? bridgeA : bridgeB;
        BridgeToken sourceToken = fromA ? tokenA : tokenB;
        uint256 beforeSupply = sourceToken.totalSupply();
        uint256 beforeNonce = source.nextNonce();
        vm.prank(PAUSER);
        source.pause();
        vm.prank(fromA ? ALICE : BOB);
        (bool ok,) = address(source).call(
            abi.encodeCall(Bridge.requestTransfer, (fromA ? CHAIN_B : CHAIN_A, fromA ? BOB : ALICE, uint256(1)))
        );
        assertTrue(!ok, "paused request rejected");
        assertEq(sourceToken.totalSupply(), beforeSupply, "paused request supply unchanged");
        assertEq(source.nextNonce(), beforeNonce, "paused request nonce unchanged");
        vm.prank(ADMIN);
        source.unpause();
        ++pauseChecks;
    }

    function revokedExecutor(bool toB) external {
        vm.chainId(toB ? CHAIN_B : CHAIN_A);
        Bridge destination = toB ? bridgeB : bridgeA;
        BridgeToken destinationToken = toB ? tokenB : tokenA;
        uint256 beforeSupply = destinationToken.totalSupply();
        vm.prank(ADMIN);
        destination.revokeRole(keccak256("EXECUTOR_ROLE"), EXECUTOR);
        vm.prank(EXECUTOR);
        (bool ok,) = address(destination).call(
            abi.encodeCall(
                Bridge.completeTransfer,
                (
                    toB ? CHAIN_A : CHAIN_B,
                    address(toB ? bridgeA : bridgeB),
                    address(toB ? tokenA : tokenB),
                    uint256(0),
                    uint256(1),
                    toB ? BOB : ALICE
                )
            )
        );
        assertTrue(!ok, "revoked executor rejected");
        assertEq(destinationToken.totalSupply(), beforeSupply, "revoked executor did not mint");
        vm.prank(ADMIN);
        destination.grantRole(keccak256("EXECUTOR_ROLE"), EXECUTOR);
        ++revokedRoleChecks;
    }

    function pendingAmountAndCheckIds() external view returns (uint256 pending) {
        for (uint256 i; i < intents.length; ++i) {
            Intent memory intent = intents[i];
            Bridge destination = intent.fromA ? bridgeB : bridgeA;
            assertTrue(destination.processed(intent.id) == intent.completed, "processed matches independent queue");
            if (!intent.completed) pending += intent.amount;
        }
    }
}

contract BridgeInvariantTest is TestSupport {
    uint256 internal constant INITIAL_EACH = 1_000_000 ether;
    BridgeToken internal tokenA;
    BridgeToken internal tokenB;
    BridgeHandler internal handler;
    address[] internal invariantTargets;

    function setUp() public {
        address admin = address(0xA11);
        address pauser = address(0xBA0);
        address executor = address(0xE1);
        vm.warp(1_700_000_000);
        vm.chainId(31337);
        tokenA = new BridgeToken("Invariant A", "IA", admin, address(0xA1), INITIAL_EACH);
        Bridge bridgeA = new Bridge(address(tokenA), admin, pauser, executor, 1_000 ether, 1_000_000_000 ether, 3600);
        vm.chainId(31338);
        tokenB = new BridgeToken("Invariant B", "IB", admin, address(0xB0B), INITIAL_EACH);
        Bridge bridgeB = new Bridge(address(tokenB), admin, pauser, executor, 1_000 ether, 1_000_000_000 ether, 3600);
        vm.startPrank(admin);
        tokenA.grantRole(keccak256("BRIDGE_ROLE"), address(bridgeA));
        tokenB.grantRole(keccak256("BRIDGE_ROLE"), address(bridgeB));
        bridgeB.configurePair(31337, address(bridgeA), address(tokenA), 18);
        vm.chainId(31337);
        bridgeA.configurePair(31338, address(bridgeB), address(tokenB), 18);
        vm.stopPrank();
        vm.prank(address(0xA1));
        tokenA.approve(address(bridgeA), type(uint256).max);
        vm.prank(address(0xB0B));
        tokenB.approve(address(bridgeB), type(uint256).max);
        handler = new BridgeHandler(tokenA, tokenB, bridgeA, bridgeB);
        invariantTargets.push(address(handler));
        // A fixed successful prefix makes the conservation check non-vacuous from its first call.
        handler.sendA(1 ether);
        handler.sendB(2 ether);
        handler.deliver(0);
    }

    function targetContracts() public view returns (address[] memory) {
        return invariantTargets;
    }

    function invariantSupplyPlusTransitEqualsBootstrapReference() public view {
        assertEq(
            tokenA.totalSupply() + tokenB.totalSupply() + handler.inTransit(),
            2 * INITIAL_EACH,
            "global supply + transit"
        );
        assertEq(
            handler.sourceBurned() - handler.destinationMinted(), handler.inTransit(), "ghost burn/mint accounting"
        );
        assertTrue(handler.requests() >= 2 && handler.completions() >= 1, "successful prefix exercised");
    }

    function invariantUniqueEffectsAndPendingPopulation() public view {
        assertEq(handler.pendingAmountAndCheckIds(), handler.inTransit(), "pending population contains each burn once");
        assertTrue(handler.completions() <= handler.requests(), "no fabricated completions in this model");
    }

    function testAllHandlerActionsAreReachable() public {
        handler.deliver(1);
        handler.duplicate(0);
        handler.pausedRequest(true);
        handler.revokedExecutor(true);
        assertEq(handler.completions(), 2, "both directions delivered");
        assertEq(handler.duplicateChecks(), 1, "duplicate scenario reached");
        assertEq(handler.pauseChecks(), 1, "pause scenario reached");
        assertEq(handler.revokedRoleChecks(), 1, "role scenario reached");
        assertEq(handler.inTransit(), 0, "initial queue drained");
    }
}
