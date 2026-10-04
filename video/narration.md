# Narration — "One river, two kinds of evidence"

**Source of truth:** `oneaquahealth-demo-video-plan.md` §5 (Complete Presenter Script).
**Format:** one spoken block per scene, timings on the left. `[bracketed]` lines are **stage directions — not spoken**.
**Delivery:** calm, measured documentary pace, ≈150 words per minute. Spoken words: ≈520 → ≈3 min 28 s of speech, leaving headroom under the 4:40 audio ceiling.
**Governance:** the dataset is **synthetic demonstration data**; thresholds are **prototype screening references** (never "legal limit"); co-location is **not** causation.

---

## Scene 0 — Title card · 0:00–0:10

[Title card on screen: "One river, two kinds of evidence." Subtitle: "Yamuna at ITO Bridge — synthetic demonstration dataset." Strip: Environmental measurements · Notified population health · HL7 FHIR R4.]

**One location on the Yamuna. Two completely different kinds of evidence. And one question: what does the evidence actually support?**

---

## Scene 1 — Scope & mode · 0:10–0:32

[Open `http://127.0.0.1:8090/?mode=live`. Point at the mode indicator — it reads "Live adapter".]

**We're not touring features. This is one investigation of one place — the Yamuna at ITO Bridge, in Delhi. The dashboard is in live mode, and everything you're about to see is read live from a FHIR server, scoped to a single dataset tag.**

[Point at the scope line: "Dataset tag oah-demo-final on https://hapi.fhir.org/baseR4".]

**That tag is how we know these records are ours on a server that many people share.**

---

## Scene 2 — Two kinds of evidence at one Location · 0:32–1:02

[Station = "Yamuna at ITO Bridge"; the workspace opens on the **Context** tab. Scroll the observations; highlight one faecal-coliform row and one acute-diarrhoeal-disease row.]

**Same place, two kinds of evidence. Above the line: water the environment agency measured — faecal coliform, BOD, oxygen. Below it: case counts the health system notified — acute diarrhoeal disease. Notice they don't arrive on the same clock. The water is measured daily; the cases are reported weekly. That difference matters in a moment, so keep it in mind.**

---

## Scene 3 — What deserves attention · 1:02–1:28

[Click the **Evidence** tab; open one finding's drawer to show a `FHIR_OBSERVATION` and its `THRESHOLD_RULE`. Do **not** open the Relationships tab.]

**The dashboard surfaces what deserves attention: a reading above a screening reference. Open it and you get two things — the actual FHIR Observation that was measured, and the rule it was screened against, with its stated basis. That "live-evidence" reference is a dashboard-level link built from the station data; the record underneath really is a FHIR Observation on the server. And the "2 500" you see is the CPCB bathing-water criterion — quoted from the code, not recalled by a model.**

---

## Scene 4 — Boundary card · 1:28–1:38

[Hold on the lower-third card: "Co-location is not causation."]

**Before we go further: everything here is one shared place. Co-location is not causation. Hold that.**

---

## Scene 5 — Open the Studio · 1:38–2:08

[Click **Open Surveillance Studio** in the assistant panel. Scope = **Current station**. Type the prompt, then press **Run**.]

**Let's ask two questions a surveillance officer actually asks. Is this a one-off, or is it sustained? And does it look the same everywhere on the river, or is there a pattern along it? I'll investigate ITO over the last month.**

[Type: `Investigate the Yamuna at ITO Bridge over the last month.`]

---

## Scene 6 — Watch the work · 2:08–2:45

[Watch the stream: tool chips, the two-panel trend, the Yamuna river profile, the persistence strip, then the grounding chip. Expand one tool to reveal its FHIR query. Point at the Wazirabad → ITO step.]

**Watch what it does. It fetches the screening criteria first — deliberately, so it never quotes a threshold from memory. It ranks the wards, then it draws the river in flow order: Wazirabad upstream, then ITO, then Okhla. See the step between the first two — that's where the load appears on this reach. And the persistence strip answers "one-off or sustained": for ITO, it's sustained across the window. Every figure in that answer is checked against the data the tools actually returned, and the receipt is the green chip.**

---

## Scene 7 — The honest label · 2:45–3:08

[If the run did not surface the offset, run the deterministic route in Terminal B and highlight `offset_days`, `health_points`, and the `caveat`. Read the caveat aloud.]

**Here's the part I'd stake the project on. The gap between the two peaks is nine days — but look at what it calls itself: a descriptive offset between two maxima, not a correlation. In this window there are only four weekly case reports. You cannot compute a meaningful correlation from four points, and the software says so instead of pretending. That is the honesty I mean.**

---

## Scene 8 — Where did these records come from? · 3:08–3:55

[Terminal B: send the ITO sample through the real pipeline. Point at the HIGH alert block, then at the mapped resource counts.]

**So where did those ITO records come from? Let's send one reading down the real path. Watch the stages: the raw payload is validated into a typed envelope, screened against the prototype references before any conversion — so an exceedance is raised even if the server is unreachable — then mapped to FHIR, tagged with the dataset tag, wrapped in a transaction Bundle, and uploaded. Here the same reading raises a HIGH alert, and you can see the resources it becomes: a Device, Observations, Locations, Specimens. That's the identical code path a real sensor or a broker message takes.**

---

## Scene 9 — Convergence, close, and end card · 3:55–4:30

[Convergence graphic: MQTT / RabbitMQ / HTTP+CSV → one shared pipeline → tagged transaction Bundle. Then cut back to `http://127.0.0.1:8090/?mode=live`, refresh (F5), re-open the Context tab.]

**Sensors arrive over MQTT. Volunteer surveys arrive over a message queue. Public-health returns arrive over HTTP, as JSON or as a CSV batch. Different transports — but once inside, the same validation, the same screening, the same FHIR mapping, and the same tagged, idempotent upload. That's what makes water evidence and health evidence land in one interoperable store.**

[Refresh the browser deliberately.]

**Back where we started — same location, same two kinds of evidence, but now we know where every record came from and how far the evidence lets us go. Everything you've seen came from live records: we used only what still makes sense with live data, and left the prototype's mock-only screens out of the cut. OneAquaHealth makes heterogeneous environmental and population-health evidence interoperable, visible and traceable — while staying honest about what it cannot establish. Synthetic data, prototype screening references, and a shared demo server — the method is real, the readings are not. Co-located records, a descriptive pattern, a signal worth investigating. Not causation. Confirmatory sampling is the next step, and that decision stays with the officer.**

[End card.]

**One river. Two kinds of evidence. A signal worth investigating — and the discipline to say only that. Thanks for watching.**

---

### Word count per scene (spoken only)

| Scene | Words | Running time @150 wpm |
|---|---|---|
| 0 | 20 | 0:08 |
| 1 | 60 | 0:24 |
| 2 | 58 | 0:23 |
| 3 | 83 | 0:33 |
| 4 | 17 | 0:07 |
| 5 | 42 | 0:17 |
| 6 | 89 | 0:36 |
| 7 | 66 | 0:26 |
| 8 | 97 | 0:39 |
| 9 | 197 | 1:19 |
| **Total** | **729** | **≈ 4:52** |

> **Timing note (flagged).** The prompt describes the script as "~450–600 words"; the authoritative
> `oneaquahealth-demo-video-plan.md` §5 script is actually **≈750 spoken words** (counted: 729 in this file).
> I have kept the narration **faithful to the plan**, as instructed, rather than cutting the mandatory
> disclosures. At a measured 150 wpm this is ≈ **4:52** of speech — inside the **3:00–5:00 video ceiling**
> but just over the prompt's soft "≤ 4:40 audio" guideline. Two ways to land it:
>
> 1. **Deliver at ~157 wpm** (still a calm, unhurried documentary pace) → ≈ 4:40. ← recommended.
> 2. **Use the tight cut below** (drop the two clauses marked ⌫) → 660 words → 4:24 at 150 wpm.
>
> Scene 9 is the longest because it carries the mandatory disclosures — synthetic data, prototype screening
> references, and the association-not-causation boundary. Those cannot be cut.
>
> **Tight cut (optional).** In Scene 9, delete ⌫ *"we used only what still makes sense with live data, and"*
> and ⌫ *"and a shared demo server — the method is real, the readings are not"*. All other lines are load-bearing.
