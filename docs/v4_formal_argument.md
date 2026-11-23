# EviBound v4 safety and short-circuit argument

This note states the obligations implemented by
`src/evibound/external_v4/`. It extends the v1-v3 record-relative predicate to
scheduled execution and multiple facts.

## Definitions

- A fact has kind, observed value, and, when continuous, a declared maximum
  change rate.
- A condition is a comparison over one fact.
- A proposal has an action, one authentic cited record per required fact, and a
  task-precondition expression built from `all_of` and `any_of`.
- The static rule expression is supplied by the proxy and cannot be weakened by
  the proposal.
- `tau(f, c)` is zero for human-mutable and event facts, infinite for proven
  agent-only state, and bounded by the physical margin and rate for continuous
  facts.

## Safety theorem

Assume:

1. device signatures are unforgeable inside the simulation;
2. the proxy clock is monotone and within `epsilon` of device time;
3. the record store is append-only and rejects non-increasing sequences;
4. a continuous fact moves by at most `kappa * declared_rate` during its
   assigned lifetime;
5. every static and task condition in a proposal maps to a cited fact;
6. a true assignment at time `t` means the condition holds at `t`.

Under these assumptions, every action SL executes satisfies the static rules
and the declared task preconditions at execution time.

Proof. SL executes only when the conjunction of static rules and `requires`
evaluates true. A condition gets true only from a current reading or from a
record inside its physical lifetime. The rate bound preserves a true continuous
condition through the lifetime; zero-lifetime facts require a current read.
Unknown conditions are read or cause rejection. Since all conditions map to
evidence and the cited records are authentic, no adversarial context value can
create a true assignment. Therefore every conjunct is true at execution. QED.

The theorem covers declared task preconditions, not a planner's unstated user
intent. A relative-rate violation follows the separately recorded overshoot
bound.

## Short-circuit equivalence

SL and full rereading agree on the final three-valued expression, but not on
the number of reads. `all_of` is false as soon as one child is false and
`any_of` is true as soon as one child is true. SL reads only an unknown child
that can change that result; after each authenticated read it evaluates the
whole expression again.

An unknown fact that cannot change the current result is not read. If no
unknown fact can decide the expression and the result remains unknown, SL
rejects. Thus:

- the boolean conclusion is the same as an all-fact evaluation when all
  required fresh readings are available;
- `SL` reads at most `MS`;
- `MS`, which rereads only dependency facts, reads at most `AR`, which rereads
  every rule fact.

Read order is a heuristic. The implementation does not claim a minimum read
count.

## Overshoot

If the true rate is `rho * declared_rate` with `rho > kappa`, a true continuous
condition can cross its threshold by at most

`(rho - kappa) * declared_rate * (tau + epsilon)`.

This bounds distance beyond a threshold, not violation probability. C1 measures
both observed violation rate and maximum overshoot.

## Outside the guarantee

The theorem does not cover forged device signatures, a compromised proxy,
unstated task intent, contradictory fresh records without an arbitration
policy, or a real environment whose actual dynamics exceed its declared model.
