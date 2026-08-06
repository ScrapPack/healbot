# The frontier query: the ONE implementation of the wayfinder blocking rule.
#
#   awk -f .scratch/frontier.awk .scratch/*/tickets/*.md | sort
#   awk -v mode=claims -f .scratch/frontier.awk .scratch/*/tickets/*.md | sort
#
# Prints every takeable ticket: open, unblocked, and unassigned. A ticket is unblocked when
# every ticket in its "Blocked by" list is closed. Ticket format: docs/agents/issue-tracker.md.
#
# `mode=claims` prints the OTHER half of the same header block: every OPEN ticket that IS
# assigned, with its holder, blocked or not — a claim is a claim whatever it waits on. It is
# here rather than in the caller for the same reason the blocking rule is: the header block has
# one reader. A renderer that wanted both would otherwise grow a second parser of the format,
# and the two would disagree about what `Assignee: -` means on the day someone writes `Assignee:`
# with nothing after it. Unknown modes REFUSE (exit 2) instead of falling back to the frontier,
# because a typo that silently prints takeable work as though it were claimed work is the same
# class of silent-wrong-answer this file's own history records below.
#
# The rule lives here and nowhere else. Anything that renders the frontier (a cockpit verb, the
# /orient command) calls this file rather than reimplementing it, because two implementations of
# one rule will disagree and the disagreement will be silent.
#
# Keys are <effort>/<number>, so two efforts may both have a ticket 01 and blockers resolve within
# the effort that names them. Numbers are read from the filename, leading zeros stripped, so
# "Blocked by: 03" and a file named 3-foo.md are the same ticket.
#
# TESTED 2026-08-05 on .scratch/daily-driver AS IT STOOD AT 829d525, the commit that added this
# file, with 01 through 06 open: baseline frontier 1,3,5,6,7; closing 03 admits 4 and 8 and drops
# 03; assigning 05 drops it. Both controls in both directions.
#
# Those numbers are a RECORD OF THAT RUN, not a standing expectation, and re-running the command
# against today's tree gives a different and equally correct answer. Said explicitly because the
# original wording read as reproducible and stopped being so within hours, when 01, 03 and 06
# closed (caught by the model review of the 7bd4085 push). Whether the query is right is settled
# by the two controls above, both of which are about the RULE and neither of which depends on how
# many tickets happen to be open.

BEGIN {
  if (mode == "") mode = "frontier"
  if (mode != "frontier" && mode != "claims") {
    printf "frontier.awk: unknown mode \"%s\" (use frontier or claims)\n", mode > "/dev/stderr"
    # `exit` in BEGIN still runs END, so the flag is what stops END printing a frontier over
    # a refused invocation. MEASURED 2026-08-05 on awk version 20200816 (the BSD awk this Mac
    # ships): stripping the flag changes neither the status (2) nor the output (empty), because
    # exit in BEGIN also skips the input, so `seen` is empty and END has nothing to print. It
    # stays because that emptiness is an accident of where the guard sits, not a property of
    # the refusal, and END is the one place a later edit would print unconditionally.
    bad = 1
    exit 2
  }
}

FNR == 1 {
  p = FILENAME
  e = p; sub(/\/tickets\/[^\/]*$/, "", e); sub(/.*\//, "", e)
  n = p; sub(/.*\//, "", n); sub(/-.*/, "", n); sub(/\.md$/, "", n); sub(/^0+/, "", n)
  k = e "/" n
  seen[k] = 1
}

# First occurrence only: the header block wins over any later line that looks like it.
/^# /          && !(k in title) { x = $0; sub(/^#[ ]+/, "", x);          title[k] = x }
/^Status:/     && !(k in st)    { st[k]  = $2 }
/^Assignee:/   && !(k in asg)   { asg[k] = $2 }
/^Blocked by:/ && !(k in blk)   { x = $0; sub(/^Blocked by:[ ]*/, "", x); blk[k]  = x }

END {
  if (bad) exit 2
  for (k in seen) {
    if (st[k] != "open") continue
    e = k; sub(/\/.*/, "", e)
    n = k; sub(/.*\//, "", n)
    if (mode == "claims") {
      if (asg[k] == "-" || asg[k] == "") continue
      printf "%-16s %2s. %s  [%s]\n", e, n, title[k], asg[k]
      continue
    }
    if (asg[k] != "-") continue
    ok = 1
    c = split(blk[k], d, /[, ]+/)
    for (i = 1; i <= c; i++) {
      b = d[i]; sub(/^0+/, "", b)
      if (b != "" && b != "-" && st[e "/" b] != "closed") ok = 0
    }
    if (ok) printf "%-16s %2s. %s\n", e, n, title[k]
  }
}
