# Design it twice

Use this only for a consequential interface with more than one credible shape.

1. State constraints, dependency categories, required invariants, error modes, and the current
   seam. A small sketch may clarify the problem but must not preselect the answer.
2. Produce at least two materially different interfaces. When parallel agents are authorized and
   available, one can minimize surface area while another optimizes the common caller or adapter
   flexibility. Otherwise, explore the alternatives sequentially.
3. For each design, show caller usage, hidden implementation, adapters, and trade-offs.
4. Compare designs by depth, locality, seam placement, migration cost, and verification surface.
5. Recommend one design or a concrete hybrid. Do not leave the user with an unranked menu.
