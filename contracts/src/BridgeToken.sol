// SPDX-License-Identifier: MIT
pragma solidity 0.8.30;

import {ERC20} from "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import {AccessControl} from "@openzeppelin/contracts/access/AccessControl.sol";

/// @notice Dedicated test token: 18 decimals, no fee, no rebase, no upgrade hook.
/// @dev DEFAULT_ADMIN_ROLE can grant BRIDGE_ROLE and thereby authorize arbitrary minting.
contract BridgeToken is ERC20, AccessControl {
    bytes32 public constant BRIDGE_ROLE = keccak256("BRIDGE_ROLE");

    error InvalidAddress();

    constructor(
        string memory name_,
        string memory symbol_,
        address admin,
        address initialRecipient,
        uint256 initialSupply
    ) ERC20(name_, symbol_) {
        if (admin == address(0) || initialRecipient == address(0)) revert InvalidAddress();
        _grantRole(DEFAULT_ADMIN_ROLE, admin);
        _mint(initialRecipient, initialSupply);
    }

    function decimals() public pure override returns (uint8) {
        return 18;
    }

    function mint(address recipient, uint256 amount) external onlyRole(BRIDGE_ROLE) {
        _mint(recipient, amount);
    }

    /// @dev The holder must approve the calling bridge; role alone cannot burn holder funds.
    function burnFrom(address account, uint256 amount) external onlyRole(BRIDGE_ROLE) {
        _spendAllowance(account, _msgSender(), amount);
        _burn(account, amount);
    }
}
