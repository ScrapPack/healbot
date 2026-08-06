# Measure the Claude-side retirement marker, or keep hand-off-early as policy

Type: grilling
Mode: HITL
Status: open
Assignee: -
Blocked by: -

## Question

The Claude half of the harness ships **no verified retirement threshold**, deliberately. The working
marker is roughly 300,000 tokens of occupancy, about 30 percent of the 1M window, carried in the
`/firstmate` skill and classified INFERRED, not measured. `NEXT.md`'s `DECIDED` section is explicit
that the opencode numbers do not transfer and that no threshold is verified for any Claude model.

Why it lands on this map: a daily driver runs long sessions and hits this constantly. Today the
policy is retire-early by judgment, and judgment under an unmeasured marker either wastes context or
walks into the ceiling, which with auto-compaction off is a hard error rather than a degradation.

The decision:

- **Measure it.** This needs a session driven to occupancy near the marker, which is paid, and is not
  another fleet bring-up run. `/paid-run-protocol` before anything here, and the captain authorizes
  the spend.
- **Keep the policy.** Accept retire-early as permanently unmeasured, and say so where the number
  appears so nobody later reads 300,000 as measured.
- **Instrument instead of measuring.** The fleet already reads live occupancy per crewmate. A
  recorded ceiling event, when one eventually happens, is free evidence that a deliberate run would
  have paid for.

The third option is cheapest and slowest and is probably right for a daily driver, but that is the
captain's call and the trade is real: it means the first real measurement arrives as a failure.

Do not resolve this by copying the opencode figure. That is already ruled out in `DECIDED`.
