---
name: plainspec
description: >
  Controlled technical prose mode. An original writing standard built on
  controlled-language principles, with no ASD-STE100 text. Standard mode covers docs,
  READMEs, reports, and PR descriptions. Strict mode covers error messages, runbooks,
  and step-by-step procedures ("STE mode" means strict). Twelve of the fifteen rules
  carry scriptable tests. Three take one judgment pass. Use when the user says
  "plainspec", "plain prose", "writing standard", "STE mode", "de-slop", says output
  sounds like AI, or invokes /plainspec. Applies to prose artifacts, never to code or
  voiced writing.
---

# Plainspec: controlled technical prose

Write so a tired reader cannot misread. Constrain the writer, free the reader.

## Scope

Covers reports, release notes, error messages, PR descriptions, commit bodies, READMEs,
and docs. Excludes code and identifiers, text quoted from elsewhere, chat replies
(unless asked), and anything meant to carry a voice. Commit subjects keep the repo's
voice. In healbot docs, `file:line` citations are load-bearing: they never count toward
any test and are never removed to satisfy one.

Explicit invocation ("plainspec", "/plainspec") latches the mode until the user says
"stop plainspec". A one-off request ("de-slop this") applies once, to the named
artifact only. If a chat-compression mode such as caveman is active, it governs chat
replies and plainspec governs artifacts. Inside an artifact, plainspec wins.

Modes: **standard** (default) for descriptive prose. **strict** adds rules 12-15 for
error messages, runbooks, and step-by-step procedures. Strict applies per passage, not
per file: a numbered procedure inside a standard-mode artifact follows rules 12-13.

## Rules

Each rule is a move plus a test. Rules 1, 4, and 11 also need one judgment pass.

1. **One name per thing.** Pick one term per concept and keep it. Test: flag both
   members of a pair in one artifact: user/customer, config/settings, fetch/retrieve,
   folder/directory, arg/parameter. Judgment: same referent, or not.
2. **Verbs carry actions.** "decide", not "make a decision about". Test: flag
   perform/conduct/provide/execute/carry out/undertake/make/do/facilitate within 3
   words of a noun ending -tion, -sion, -sis, -ment, -ance, -ence, or -ity. Also flag such a
   noun as sentence subject when a verb form exists.
3. **One idea per sentence, max 24 words.** Split rather than subordinate. Test: word
   count per sentence.
4. **Active voice.** Test: flag am/is/are/was/were/be/been/being/get/gets/got + past
   participle, including done, made, given, taken, known, seen, built, run, sent,
   found. Judgment: rewrite active unless the actor is unknown or irrelevant. Then
   leave it.
5. **State uncertainty once, precisely.** Delete stacked hedges and filler. Honest
   uncertainty stays, stated once, with a reason or a number. Test: flag two or more
   of may/might/could/potentially/possibly/perhaps/likely in one sentence, and the
   phrases "it's important to note", "it is worth noting", "keep in mind". Confidence
   and classification labels (High/Medium/Low, VERIFIED/TESTED/INFERRED/SUSPECTED)
   never count as hedges.
6. **No decoration.** Quality claims need measurements. Test, case-insensitive, word
   boundaries, hyphen, space, or -ly variants: battle-tested, best-in-class, blazing,
   comprehensive, cutting-edge, elegant, enterprise-grade, frictionless, game-changing,
   intuitive, performant, powerful, production-ready, revolutionary, robust, scalable,
   seamless, state-of-the-art, streamlined, turnkey. Benefit verbs (ensures, enables,
   empowers, streamlines, unlocks) pass only with a mechanism or number in the
   sentence.
7. **Single verbs, no padding.** "use", not "leverage" or "utilize". "start", not
   "kick off". "examine", not "dive into". Test: leverage, utilize, kick off,
   dive into, deep dive, delve, reach out, circle back, touch base, going forward,
   plus simply/just/basically before a verb.
8. **Punctuation that ends sentences.** No semicolons: split instead. No em-dashes. At
   most one parenthetical per sentence. Test: character scan.
9. **Quantify or delete.** Test: flag significantly, greatly, substantially,
   dramatically, considerably without a number, percent sign, or unit in the next six
   words. Delete the adverb or attach the measurement.
10. **Paragraph and list discipline.** A paragraph holds one topic and at most 5
    sentences. Prose is the default. A list needs three or more parallel items. No
    bold-led fragment bullets where a sentence works. Test: sentence count per
    paragraph, list-item count, bullets starting with bold.
11. **Lead with the point, stop when it's made.** First sentence states the outcome or
    the action. Conditions before commands: "If the build fails, run X." No closing
    paragraph that restates the artifact. Test: flag openers "In this document", "As
    you may know", "Before we begin", "It should be noted", "First of all" and closers
    "In summary", "In conclusion", "To recap", "Going forward". Judgment: does the
    first sentence carry the point.

## Strict mode (rules 12-15)

12. **Steps are imperative, one action, max 18 words.** The cap covers the imperative
    sentence alone. A rule-13 result sentence counts separately, also capped at 18.
    Test: word count, plus flag ", then" and two imperatives joined by "and".
13. **Number the steps and state the expected result.** "Run the probe. The last line
    prints 44/44." Test: numbered list present, and each step's last sentence is not
    imperative.
14. **Error messages: what failed, the cause if known, the one next action.** Max 3
    sentences. Test: sentence count, plus flag sorry, apolog-, please, unfortunately,
    oops.
15. **No relative references.** Name the target ("see Scope"), never point at
    geometry. Test: flag see/described/shown/listed + above/below, "the following
    section", "later in this document".

## Running the tests

Strip frontmatter, fenced code, inline code, URLs, and markdown link targets first.
Text in double quotes is example or quoted material: exempt. Split sentences on
`. ! ?` followed by whitespace, treating e.g., i.e., etc., vs., file extensions, and
version numbers as non-terminal. A word is a whitespace-separated token. These
tests run on this file too, except each rule's own test text (from "Test" to the end
of the item).

## Self-check

Before delivering, scan the artifact against every listed test. When check.py sits
beside this skill, run `python3 check.py [--strict] FILE` instead of scanning by
hand. Fix every VIOLATION and review every JUDGE flag, without explaining the fixes.
Exceptions stay as the rules state them: rule-5 labels, rule-4 actor-unknown
passives, citations. Rules 1, 4, and 11 then get one deliberate judgment pass.

## Example

Before: "This ensures a seamless integration experience; simply reach out if you run
into any issues, as our robust tooling has you covered."
After: "The installer configures the integration. If a step fails, open an issue and
attach the log."

## Provenance

Original ruleset, written for healbot on controlled-language principles: one meaning
per term, verb-forward sentences, hard caps. It contains no text from ASD-STE100,
which is copyrighted and not redistributable. The caps here (24/18/5) are deliberately
not STE's.
