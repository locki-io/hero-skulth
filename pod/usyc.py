"""USYCVault — the ONE inspected venue (skulth#4 N2 ratified, N4 built).

Layered against invention (Confirm rule #1 — the mirror's corrupted
address taught us): `USYCVault` implements the Venue protocol against a
`TellerClient` interface and is fully testable offline; the concrete
`Web3TellerClient` carries ONLY verified surfaces tonight — standard
ERC-20 reads and chain facts. The Teller's buy/sell/price ABI is NOT
guessed: those methods raise until the ABI is read from the verified
contract at testnet.arcscan.app (follow-up flagged on skulth#4).

Yield mechanics (primary source, circle.com/usyc): USYC accrues via a
RISING PRICE — no staking, no claiming. The venue's own price is the
yield oracle: earned = holdings × Δprice, harvested to USDC by selling
the gain. Deterministic in tests via an injected price.

Addresses — primary source docs.arc.io/arc/references/contract-addresses
(fetched 2026-07-20; per Confirm rule #1 no address enters config from
any secondary surface):
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional, Protocol

USDC_ADDRESS = "0x3600000000000000000000000000000000000000"  # native, 6 decimals
USYC_ADDRESS = "0xe9185F0c5F296Ed1797AaE4238D26CCaBEadb86C"
TELLER_ADDRESS = "0x9fdF14c5B14173D74C08Af27AebFf39240dC105A"
ENTITLEMENTS_ADDRESS = "0xcc205224862c7641930c87679e98999d23c26113"
CHAIN_ID = 5042002

ERC20_ABI = [  # standard fragment — safe to declare, universally verified
    {
        "name": "balanceOf",
        "type": "function",
        "stateMutability": "view",
        "inputs": [{"name": "account", "type": "address"}],
        "outputs": [{"name": "", "type": "uint256"}],
    },
]


class NotEntitled(RuntimeError):
    """The Entitlements contract says this address may not hold USYC."""


class TellerClient(Protocol):
    def usdc_balance_micro(self) -> int: ...

    def usyc_balance_micro(self) -> int: ...

    def price_micro(self) -> int: ...  # USDC micro per 1.000000 USYC

    def buy_usyc(self, usdc_micro: int) -> int: ...  # returns USYC micro received

    def sell_usyc(self, usyc_micro: int) -> int: ...  # returns USDC micro received

    def is_entitled(self) -> Optional[bool]: ...  # None = unknown (ABI pending)


class USYCVault:
    """Venue-protocol adapter: deposit mints USYC, accrual harvests the
    price gain back to USDC. Position state persists like every organ's."""

    venue_id = "usyc"
    MIN_HARVEST_MICRO = 1_000  # dust gate: gains below 0.001 USDC ride to next epoch

    def __init__(self, teller: TellerClient, state_dir: Path) -> None:
        self.teller = teller
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self._file = self.state_dir / "usyc.json"
        if self._file.exists():
            state = json.loads(self._file.read_text())
            self.usyc_micro = state["usyc_micro"]
            self.last_price_micro = state["last_price_micro"]
        else:
            self.usyc_micro = 0
            self.last_price_micro = 0

    @property
    def principal_micro(self) -> int:
        """Marked to the venue's own price — the yield oracle."""
        if self.usyc_micro == 0:
            return 0
        return self.usyc_micro * self.teller.price_micro() // 1_000_000

    def deposit_micro(self, amount: int) -> None:
        entitled = self.teller.is_entitled()
        if entitled is False:  # None = unknown → the chain is the final judge
            raise NotEntitled(f"{ENTITLEMENTS_ADDRESS} refuses this address")
        received = self.teller.buy_usyc(amount)
        self.usyc_micro += received
        self.last_price_micro = self.teller.price_micro()
        self._persist()

    def accrue_micro(self, epoch: int) -> int:
        """Harvest the price gain since last mark, realized to USDC."""
        if self.usyc_micro == 0:
            return 0
        price = self.teller.price_micro()
        gain_usdc = self.usyc_micro * (price - self.last_price_micro) // 1_000_000
        if gain_usdc < self.MIN_HARVEST_MICRO:
            return 0  # mark stays — dust accumulates until worth a sell
        usyc_to_sell = gain_usdc * 1_000_000 // price
        received = self.teller.sell_usyc(usyc_to_sell)
        self.usyc_micro -= usyc_to_sell
        self.last_price_micro = price
        self._persist()
        return received

    def _persist(self) -> None:
        tmp = self._file.with_suffix(".tmp")
        tmp.write_text(
            json.dumps({"usyc_micro": self.usyc_micro, "last_price_micro": self.last_price_micro})
        )
        tmp.replace(self._file)


class Web3TellerClient:
    """Verified surfaces only. ERC-20 reads work today; Teller trade calls
    raise until the verified ABI is fetched from testnet.arcscan.app."""

    def __init__(self, rpc_url: str, pod_address: str) -> None:
        from web3 import Web3  # the ONE admitted dependency (P2 gauntlet)

        self.w3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={"timeout": 10}))
        self.pod_address = Web3.to_checksum_address(pod_address)

    def chain_id(self) -> int:
        return self.w3.eth.chain_id

    def _erc20_balance(self, token: str) -> int:
        from web3 import Web3

        contract = self.w3.eth.contract(Web3.to_checksum_address(token), abi=ERC20_ABI)
        return contract.functions.balanceOf(self.pod_address).call()

    def usdc_balance_micro(self) -> int:
        return self._erc20_balance(USDC_ADDRESS)

    def usyc_balance_micro(self) -> int:
        return self._erc20_balance(USYC_ADDRESS)

    def price_micro(self) -> int:
        raise NotImplementedError("Teller ABI pending verification at testnet.arcscan.app")

    def buy_usyc(self, usdc_micro: int) -> int:
        raise NotImplementedError("Teller ABI pending verification at testnet.arcscan.app")

    def sell_usyc(self, usyc_micro: int) -> int:
        raise NotImplementedError("Teller ABI pending verification at testnet.arcscan.app")

    def is_entitled(self) -> Optional[bool]:
        return None  # Entitlements ABI pending verification — chain remains the judge


def probe() -> int:
    """Read-only chain probe: RPC, chain id, the pod's balances. No key used."""
    import os

    from pod.wallet import address as wallet_address

    rpc = os.environ.get("SKULTH_ARC_RPC_URL", "https://rpc.testnet.arc.network")
    state = Path(os.environ.get("SKULTH_POD_STATE_DIR", "state"))
    pod_address = wallet_address(state)
    if pod_address is None:
        print("probe: no wallet born in", state)
        return 1
    client = Web3TellerClient(rpc, pod_address)
    chain = client.chain_id()
    usdc = client.usdc_balance_micro()
    usyc = client.usyc_balance_micro()
    print(f"probe: chain {chain} ({'OK' if chain == CHAIN_ID else 'UNEXPECTED — expected 5042002'})")
    print(f"probe: {pod_address}")
    print(f"probe: USDC {usdc / 1_000_000:.6f} · USYC {usyc / 1_000_000:.6f}")
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(probe())
