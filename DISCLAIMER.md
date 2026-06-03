# Disclaimer — read before you use Lighthouse

Lighthouse is a research aid. It is not a medical device, not a clinician, and not a source of medical advice.

## Not medical advice

Everything Lighthouse produces — every summary, ranking, trial match, and digest — is **information to bring to a qualified care team**, not a recommendation. It does not diagnose. It does not prescribe. It does not tell anyone which treatment to pursue or avoid. It cannot predict prognosis, survival, odds, or timelines, and it will not try to.

Cancer treatment decisions belong to the patient and their doctors. Use Lighthouse to ask better questions — never to answer them on your own.

## AI can be wrong

Lighthouse uses an AI model to summarize and rank medical literature. AI models can misread studies, overstate weak evidence, miss context, or state something confidently that is incorrect. Always open the original source — Lighthouse links to it — and confirm anything important with a clinician before acting on it. Treat a Lighthouse digest as a starting point for a conversation, not as a conclusion.

## No warranty

This software is provided "as is," without warranty of any kind, as stated in the [LICENSE](LICENSE). The authors and contributors are not liable for any decision made, or harm resulting, from its use. By using Lighthouse, you accept that responsibility for any medical decision rests with you and the patient's care team.

## Privacy

Lighthouse is designed to keep patient information on the machine where you run it. You should still understand what travels off it:

- **Search queries** built from the profile go to public medical databases (PubMed, ClinicalTrials.gov, and any sources you enable). These are queries — for example, a cancer type, a biomarker, a city — not the full profile.
- **Text sent to your AI model.** To summarize and rank findings, Lighthouse sends study text and relevant profile context to whichever AI provider you configure. Read that provider's data-use and retention terms before you enter anyone's real medical information. If that's a concern, you can run a local model instead.
- **The digest** goes wherever you tell it to (your email, a private channel). Make sure that destination is one you control and trust.

The profile, idea station, and generated digests are kept out of version control by default so they are never committed to a public repository. Do not override that unless you understand the consequence. Never put a patient's full name, address, medical record number, or other direct identifiers into the profile — the research only needs the clinical facts (cancer type, stage, biomarkers, general geography).

## Use it the way it was meant to be used

Lighthouse exists to give the people caring for a cancer patient a little more time and a little less overwhelm. Keep the care team at the center. Keep the data yours. Keep your skepticism. That's how it helps.
