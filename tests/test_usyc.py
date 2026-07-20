"""USYCVault harness — the venue proven offline against a fake teller
whose price is a dial, not a die-roll.
"""

import pytest

from pod.usyc import NotEntitled, USYCVault


class FakeTeller:
    def __init__(self, price_micro=1_000_000, entitled=True):
        self._price = price_micro
        self._entitled = entitled
        self.usdc = 0
        self.usyc = 0

    def set_price(self, price_micro):
        self._price = price_micro

    def usdc_balance_micro(self):
        return self.usdc

    def usyc_balance_micro(self):
        return self.usyc

    def price_micro(self):
        return self._price

    def buy_usyc(self, usdc_micro):
        return usdc_micro * 1_000_000 // self._price

    def sell_usyc(self, usyc_micro):
        return usyc_micro * self._price // 1_000_000

    def is_entitled(self):
        return self._entitled


def test_deposit_mints_at_price(tmp_path):
    teller = FakeTeller(price_micro=1_000_000)
    vault = USYCVault(teller, tmp_path)
    vault.deposit_micro(20_000_000)  # the operator's 20 USDC
    assert vault.usyc_micro == 20_000_000
    assert vault.principal_micro == 20_000_000


def test_rising_price_marks_principal_up(tmp_path):
    teller = FakeTeller(price_micro=1_000_000)
    vault = USYCVault(teller, tmp_path)
    vault.deposit_micro(20_000_000)
    teller.set_price(1_010_000)  # +1%
    assert vault.principal_micro == 20_200_000


def test_accrue_harvests_gain_to_usdc(tmp_path):
    teller = FakeTeller(price_micro=1_000_000)
    vault = USYCVault(teller, tmp_path)
    vault.deposit_micro(20_000_000)
    teller.set_price(1_010_000)
    harvested = vault.accrue_micro(epoch=1)
    assert harvested == pytest.approx(200_000, abs=2)  # ~0.20 USDC realized
    # principal returns to ~the deposit mark after harvest
    assert vault.principal_micro == pytest.approx(20_000_000, abs=2_000)


def test_flat_price_harvests_nothing(tmp_path):
    teller = FakeTeller(price_micro=1_000_000)
    vault = USYCVault(teller, tmp_path)
    vault.deposit_micro(20_000_000)
    assert vault.accrue_micro(epoch=1) == 0


def test_dust_gains_ride_to_next_epoch(tmp_path):
    teller = FakeTeller(price_micro=1_000_000)
    vault = USYCVault(teller, tmp_path)
    vault.deposit_micro(20_000_000)
    teller.set_price(1_000_010)  # gain = 200 micro < MIN_HARVEST
    assert vault.accrue_micro(epoch=1) == 0
    teller.set_price(1_000_100)  # cumulative gain 2_000 micro ≥ MIN_HARVEST
    assert vault.accrue_micro(epoch=2) > 0


def test_refused_entitlement_blocks_deposit(tmp_path):
    vault = USYCVault(FakeTeller(entitled=False), tmp_path)
    with pytest.raises(NotEntitled):
        vault.deposit_micro(20_000_000)


def test_unknown_entitlement_defers_to_chain(tmp_path):
    vault = USYCVault(FakeTeller(entitled=None), tmp_path)
    vault.deposit_micro(1_000_000)  # chain would revert if truly refused
    assert vault.usyc_micro == 1_000_000


def test_position_persists_across_reload(tmp_path):
    teller = FakeTeller(price_micro=1_000_000)
    USYCVault(teller, tmp_path).deposit_micro(20_000_000)
    reloaded = USYCVault(teller, tmp_path)
    assert reloaded.usyc_micro == 20_000_000
