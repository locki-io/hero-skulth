// SPDX-License-Identifier: Apache-2.0
pragma solidity ^0.8.24;

/// @title RentVault — pay-or-die, enforced by code
/// @notice The on-chain half of hero-skulth's survival constraint
///         (skulth#4 LANDED criteria 2-3). One tenant pod, one rent,
///         one clock. Rent is paid per epoch in USDC; when an epoch
///         closes unpaid, ANYONE may declare the death — the contract
///         emits the death record and the tenant is dead forever.
///         Dead pods stay dead: there is no resurrection function,
///         by design and not by omission.
/// @dev    Arc testnet only. Terms are immutable at deployment — the
///         landlord cannot raise the rent mid-life, the pod cannot
///         renegotiate. Money is USDC's native 6 decimals (micro).
interface IERC20 {
    function transferFrom(address from, address to, uint256 amount) external returns (bool);
}

contract RentVault {
    IERC20 public immutable usdc;
    address public immutable tenant;    // the pod's wallet
    address public immutable landlord;  // where rent goes (the operator's cost sink)
    uint256 public immutable rentMicro; // per-epoch rent, USDC 6-decimals
    uint256 public immutable genesis;   // unix seconds, epoch 0 opens
    uint256 public immutable epochSeconds; // accelerated: 3600 = one billing day per hour

    uint256 public lastPaidEpoch; // type(uint256).max until first payment
    bool public dead;

    event RentPaid(uint256 indexed epoch, uint256 rentMicro);
    /// @notice The on-chain tombstone — queryable forever.
    event DeathRecord(
        uint256 indexed diedAtEpoch,
        uint256 lastPaidEpoch,
        string cause
    );

    error NotTenant();
    error PodDead();
    error EpochNotOpen();
    error AlreadyPaid();
    error StillSolvent();

    constructor(
        IERC20 usdc_,
        address tenant_,
        address landlord_,
        uint256 rentMicro_,
        uint256 genesis_,
        uint256 epochSeconds_
    ) {
        require(epochSeconds_ > 0 && rentMicro_ > 0, "bad terms");
        usdc = usdc_;
        tenant = tenant_;
        landlord = landlord_;
        rentMicro = rentMicro_;
        genesis = genesis_;
        epochSeconds = epochSeconds_;
        lastPaidEpoch = type(uint256).max; // sentinel: nothing paid yet
    }

    /// @notice The one clock, mirrored from pod/epoch.py — same arithmetic.
    function currentEpoch() public view returns (uint256) {
        require(block.timestamp >= genesis, "pre-genesis");
        return (block.timestamp - genesis) / epochSeconds;
    }

    /// @notice Tenant pays the currently open epoch. Requires prior USDC approval.
    function payRent() external {
        if (msg.sender != tenant) revert NotTenant();
        if (dead) revert PodDead();
        uint256 epoch = currentEpoch();
        if (lastPaidEpoch != type(uint256).max && epoch <= lastPaidEpoch) revert AlreadyPaid();
        require(usdc.transferFrom(tenant, landlord, rentMicro), "transfer failed");
        lastPaidEpoch = epoch;
        emit RentPaid(epoch, rentMicro);
    }

    /// @notice True while the pod's rent obligations are met for every closed epoch.
    function heartbeat() public view returns (bool) {
        if (dead) return false;
        uint256 epoch = currentEpoch();
        if (epoch == 0) return true; // epoch 0 still open or just closed unpaid-yet
        if (lastPaidEpoch == type(uint256).max) return false; // epoch 0 closed, never paid
        return lastPaidEpoch >= epoch - 1;
    }

    /// @notice When a closed epoch stands unpaid, ANYONE may declare the death —
    ///         insolvency is public truth, not the tenant's confession.
    function declareDeath() external {
        if (dead) revert PodDead();
        if (heartbeat()) revert StillSolvent();
        dead = true;
        emit DeathRecord(
            currentEpoch(),
            lastPaidEpoch == type(uint256).max ? 0 : lastPaidEpoch,
            "rent unpaid at epoch close"
        );
    }
}
