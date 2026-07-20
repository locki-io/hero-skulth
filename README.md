# Hero-skulth

> **Agentic inspection of smart contracts — under a survival constraint.**
> Built for the Encode × Arc Programmable Money Hackathon (Agentic Economy / DeFi tracks). Arc testnet only.

Hero-skulth is an autonomous agent pod on Arc testnet that inspects smart contracts before committing capital — and must **pay its own server rent from on-chain yield, or shut down for real.**

Most agents optimize for yield. **This one optimizes for probability of continued existence.**

## Why (explanation)

- **Inspection-gated capital.** Every deposit is blocked until a machine-checked audit bundle — audit provenance, exploit history, withdrawal latency — passes a consistency gate (`hard violation ⇒ BLOCK deposit`). No consistent bundle, no capital movement.
- **Survival-first allocation.** The Allocation Engine maximizes `P(rent paid at epoch N)`, not APY. **Abstention is a first-class, weighted decision**: idle stablecoin beats unvetted yield when runway allows. Doubt is an asset with a yield of its own — survival.
- **Death is a designed feature.** An on-chain rent contract, a heartbeat, and a death daemon: when the treasury cannot pay at epoch close, the pod writes a **verifiable death record** (final balance, cause of death, last decision), stops serving, and exits. A dead pod stays dead.
- **Cognition is a budgeted expense.** Baseline reasoning runs on local inference (free at the margin — covered by the rent it already pays). Frontier-model calls are priced in rent-epochs and must be affordable. The agent budgets its own thinking.

## The demo (tutorial — lands at build phase)

Twin pods, one billing contract, two fates, accelerated epochs (1 h = 1 billing day):

- **Twin A** earns from one inspected venue, pays rent, survives.
- **Twin B** starves, flatlines on stage — and stays on screen.

Run it yourself — one command, both fates:

```bash
git clone https://github.com/locki-io/hero-skulth && cd hero-skulth/deploy
docker compose up --build
# twin-a settles rent every 15-second epoch and lives (earns 2.70 vs 2.40 rent)
# twin-b abstains, runway counts 2 → 1 → 0, flatlines at epoch 3, exit code 3
docker compose up twin-b   # the corpse refuses restart: same tombstone, exit 3
```

The death record is at `/state/TOMBSTONE.json` inside the dead twin's volume; the full life ledger at `/state/pod-activity.jsonl`.

## Architecture (three planes)

```
data plane      →  private market/regime engine, reached ONLY via a scoped, revocable API key
decision plane  →  this repo: audit ingestion → consistency gate → allocation engine
                   → treasury → rent contract → heartbeat → death daemon
public surface  →  this repo IS the public surface; fresh history by construction
```

The pod's cognitive engine derives from a sovereign local RAG + consistency-rules architecture (retrieval and rule-checking run fully local; no external model required for baseline operation).

## Status

Plan phase complete (architecture, adversarial review, landscape benchmark); build in progress toward Demo Day. This repository will only ever contain the pod's decision plane — the private data plane is not, and will never be, in this history.

## Honesty labels

**Testnet simulation** — economics real in structure, simulated in value. The cost oracle is trusted in this iteration (stated constraint; attestation-based pricing is the named upgrade path). A human operator retains an out-of-band kill switch: autonomy inside a sovereign perimeter. **Not financial advice.**

## License

Apache 2.0 — see [LICENSE](LICENSE) and [NOTICE](NOTICE).
