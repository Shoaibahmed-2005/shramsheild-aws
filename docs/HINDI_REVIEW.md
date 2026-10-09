# Hindi review

**Status: PENDING. No native Hindi speaker has reviewed this text yet.**

Every Hindi string below is machine-drafted. It was written into the frozen contract
(docs/BUILD_PLAN.md section 3.8) when the plan was prepared and has had no native review.
Until the Reviewer columns are filled in, any writeup, demo or video must say the Hindi
text is machine-drafted and awaiting native review.

## How to use this file

1. Send the table below to a Hindi speaker (a teammate, friend or family member is fine).
   Ten minutes is enough.
2. They put OK or a suggested change on each row, and their name and the date.
3. Give the result back to the coding agent. The agent does **not** reword Hindi on its own:
   the text lives in the frozen contract, so the human edits BUILD_PLAN.md section 3.8 and
   states the exact new wording, and only then is messages.py updated to match (P1.3 step 9).

The examples are real rendered output, not templates, so the reviewer sees what a
supervisor would actually receive. The site name is the demo value "Chennai demo site".

## Questions for the reviewer

1. Is it polite and clear for a construction worker?
2. Is the speed of reading natural? (It is also read aloud by a Hindi voice.)
3. Are "सुपरवाइज़र" and "साइट" what workers actually say?
4. Is "गर्मी का खतरा" the right phrase for heat risk?
5. Is the order of information right (what to do first, then why, then the warning)?

## Text to review

| Message id | Hindi text | Reviewer OK? | Suggested change | Reviewer name | Date |
|---|---|---|---|---|---|
| HI_WINDOW (ORANGE, 12 to 3) | Chennai demo site साइट: आज दोपहर 12 बजे से दोपहर 3 बजे तक गर्मी का खतरा ज़्यादा रहेगा। सबसे ज़्यादा गर्मी दोपहर 1 बजे के आसपास होगी। इस दौरान हर घंटे में ज़्यादा से ज़्यादा 30 मिनट काम करें और कम से कम 30 मिनट छाया में आराम करें। हर 20 मिनट में लगभग एक गिलास ठंडा पानी पिएं। चक्कर, उल्टी या घबराहट हो तो तुरंत काम रोकें और सुपरवाइज़र को बताएं। | | | | |
| HI_STOP (2 to 3) | Chennai demo site साइट: आज दोपहर 2 बजे से दोपहर 3 बजे तक गर्मी का खतरा अत्यधिक रहेगा। इस समय ज़रूरी काम के अलावा बाकी सारा काम रोक दें। ज़रूरी काम भी सुपरवाइज़र की निगरानी में, छाया में और बार-बार आराम करके ही करें। हर 20 मिनट में लगभग एक गिलास ठंडा पानी पिएं। | | | | |
| HI_GREEN | Chennai demo site साइट: आज दिन भर गर्मी का खतरा कम है। पानी पास रखें और भारी काम में हर 20 मिनट में पानी पिएं। तबीयत ठीक न लगे तो काम रोककर सुपरवाइज़र को बताएं। | | | | |
| HI_UNKNOWN | Chennai demo site साइट: मौसम का डेटा अभी उपलब्ध नहीं है, इसलिए आज का गर्मी का अनुमान नहीं बन सका। छाया और पानी पास रखें, और तबीयत ठीक न लगे तो काम रोककर सुपरवाइज़र को बताएं। | | | | |
| level name GREEN | कम | | | | |
| level name YELLOW | मध्यम | | | | |
| level name ORANGE | ज़्यादा | | | | |
| level name RED | बहुत ज़्यादा | | | | |
| level name STOP | अत्यधिक | | | | |
| hour word, 00:00 to 03:00 | रात 12 बजे / रात 2 बजे / रात 3 बजे | | | | |
| hour word, 04:00 to 11:00 | सुबह 4 बजे / सुबह 9 बजे / सुबह 11 बजे | | | | |
| hour word, 12:00 to 15:00 | दोपहर 12 बजे / दोपहर 1 बजे / दोपहर 3 बजे | | | | |
| hour word, 16:00 to 18:00 | शाम 4 बजे / शाम 5 बजे / शाम 6 बजे | | | | |
| hour word, 19:00 to 23:00 | रात 7 बजे / रात 9 बजे / रात 11 बजे | | | | |

## Notes for the reviewer

- The numbers (minutes, hours, 20 minutes) are filled in by the system and change per site
  and per day. Please comment on the wording around them, not the values.
- The hour words are built as a time-of-day word plus a 12-hour number plus बजे.
  Please check that each one sounds natural at the hours shown.
- The same text is sent as a written message and spoken by a Hindi voice, so awkward
  abbreviations or English words matter twice.

