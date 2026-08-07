"""Contemporary museum-investigation records, coherent and seeded.

These seven classes are the producing-system layer for a facilitated mystery.
They deliberately do not share one visible house template: a curator's memo,
laboratory report, access-control export, property ledger, mobile-device report,
and equipment card should look as though they came from different systems.

Load-bearing source contracts (acquired at authoring time, never at render time):

* NPS Museum Handbook II, Museum Records, for accession-folder research notes,
  conservation records, record custody, and archival citation anatomy.
* NPS Museum Handbook I.14 and its Key Issuance Form for controlled-space
  access fields and custody expectations.
* NIST OSAC 2022-S-0019, Standard Guide for Forensic Examination of Fibers,
  for case assessment, evidence handling, observations, evaluation,
  limitations, documentation, and independent verification.
* Kantech EntraPass Quick/Historical Report manuals for event sequence, date
  and time, event message, card number, door/controller descriptions, filters,
  and PDF export behavior.
* New Jersey DCA Lease Information Bulletin and Truth in Renting for the
  landlord/tenant, premises, term, rent, deposit, and record-copy field world.
  This emitter is an account-system record, not a lease and not legal prose.
* Apple iPhone User Guide, "Check your voicemail," for sender/call identity,
  duration, playback/transcription, sharing, and the warning that transcription
  is a derived convenience rather than the audio itself.
* EPA CMOM and pump-station O&M guidance plus OSHA 29 CFR 1910.147 guidance for
  equipment identity, emergency procedure availability, alarm/inspection
  records, energy isolation, stored-energy warning, and verification.

The named organizations, systems, people, properties, and cases rendered by
the defaults are invented.  The structural contracts above are not.
"""

from __future__ import annotations

from copy import deepcopy
from functools import partial
import io
import random
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.graphics.shapes import Drawing, Path as DrawingPath
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from . import legalpdf


KINDS = (
    "museum_research_note",
    "curatorial_chronology",
    "conservation_examination",
    "access_event_report",
    "tenant_account_ledger",
    "voicemail_evidence_report",
    "pump_emergency_card",
)

DEFAULTS: dict[str, dict[str, Any]] = {
    "museum_research_note": {
        "organization": "Hudson Palisade History Center",
        "department": "Research & Interpretation",
        "organization_address": "14 River Street · Hoboken, New Jersey 07030",
        "record_id": "RIM-26-041",
        "repository_code": "HPHC-NJ",
        "records_series": "ER-2026-02 / inquiry 06",
        "project": "Temporary exhibition research — The Rogers Case",
        "loan_number": "L2026.002",
        "object_id": "TEMP-L2026.002.001",
        "receipt_id": "TC-2026-014",
        "lender": "Elias Crane",
        "record_status": "UNACCESSIONED TEMPORARY CUSTODY",
        "current_location": "Collections workroom CW-2 / cabinet 4 / folder 14",
        "handling_class": "Research handling only; polyester support required",
        "rights_status": "Private lender; internal research reproduction only",
        "object_description": "Private-lender packet: an 1841 newspaper clipping with a later handwritten note attached at the upper edge.",
        "object_custody": "Received 2026-02-10 from Elias Crane under temporary-custody receipt TC-2026-014; held in collections workroom cabinet CW-2 pending return.",
        "represented_date": "2026-02-11",
        "exported_at": "2026-02-11 16:42:00",
        "prepared_by": "Ada Bell, Ph.D., contract historian",
        "reviewed_by": "Miriam Quill, curator",
        "subject": "Poe, Mary Rogers, and the claimed Sybil's Cave visit",
        "question": "Does the surviving publication record support a claim that Edgar Allan Poe investigated inside Sybil's Cave?",
        "finding": "Not supported by the sources reviewed. They document Poe's use of press accounts and his fictional relocation of the Rogers case to Paris, but none supplies affirmative evidence of a visit inside Sybil's Cave. This record does not determine the authorship or date of the questioned note on examination item Q-3.",
        "sources": [
            ["S-01", "Digital scholarly transcription of Poe to George Roberts, 4 June 1842, LTR-136", "Contemporary letter text; real-case basis and press-analysis design"],
            ["S-02", "Ladies' Companion 17 (Nov. 1842): 15-20; 17 (Dec. 1842): 93-99; 18 (Feb. 1843): 162-167", "Digitized first publication; three serialized parts"],
            ["S-03", "Poe, 'The Mystery of Marie Roget,' Tales (Wiley & Putnam, 1845); EAPoe text 1845-01", "Digital scholarly transcription of revised text"],
            ["S-04", "E. A. Poe Society work record PT040, rev. 29 Apr. 2023", "Editorial publication history; manuscript-status note"],
        ],
        "source_locators": [
            "S-01 — https://www.eapoe.org/works/letters/p4206040.htm — LTR-136 — ER-WEB-26-031; captured 2026-02-11 08:54 ET",
            "S-02a — https://www.eapoe.org/works/tales/rogeta1.htm — Part I — ER-WEB-26-032; captured 2026-02-11 09:51 ET",
            "S-02b — https://www.eapoe.org/works/tales/rogeta2.htm — Part II — ER-WEB-26-033; captured 2026-02-11 09:53 ET",
            "S-02c — https://www.eapoe.org/works/tales/rogeta3.htm — Part III — ER-WEB-26-034; captured 2026-02-11 09:55 ET",
            "S-03 — https://www.eapoe.org/works/tales/rogetb.htm — 1845 text — ER-WEB-26-035; captured 2026-02-11 11:14 ET",
            "S-04 — https://www.eapoe.org/works/info/pt040.htm — work record — ER-WEB-26-036; captured 2026-02-11 13:28 ET",
        ],
        "research_log": [
            ["09:12 ET", "S-01 / ER-WEB-26-031", "Ada Bell; checked letter heading and the paragraphs beginning ‘I have handled my theme’ and ‘I examine.’"],
            ["10:05 ET", "S-02a-c / ER-WEB-26-032–034", "Ada Bell; searched Hoboken | cave | visit | New York; zero hits for Hoboken or cave; New York occurs in the tale's case framing."],
            ["11:28 ET", "S-03 / ER-WEB-26-035", "Ada Bell; repeated the same query set in the 1845 text; read every newspaper and press hit in context."],
            ["13:40 ET", "S-04 / ER-WEB-26-036", "Ada Bell; checked publication-state list and manuscript-status note; referred Q-3 to ATCL-26-00387."],
        ],
        "review_authority": "Curator delegation 2025-11 / exhibition research files",
        "reviewed_at": "11 February 2026",
        "retention": "Retain with ER-2026-02 through 2033-06; return lender object under L2026.002",
        "limitations": "The four named records were consulted as scholarly digital transcriptions or reproductions, not originals. No draft manuscript or scratch notes for the tale are known to survive. Lack of affirmative visit evidence does not prove Poe never entered Hoboken. Note authorship and date are outside scope.",
    },
    "curatorial_chronology": {
        "organization": "Hudson Palisade History Center",
        "department": "Collections & Exhibitions",
        "record_id": "CHR-26-017",
        "represented_date": "2026-02-11",
        "exported_at": "2026-02-11 21:24:00",
        "title": "Working event chronology — ER-2026-02",
        "prepared_by": "Ada Bell, Ph.D., contract historian",
        "scope": "Documented publication history compared with preview-night observations. Times are local Eastern Time unless a source states otherwise.",
        "rows": [
            ["1841-07-28", "Mary Cecilia Rogers's body is recovered from the Hudson near Weehawken.", "historical", "H-01 / NY Herald, 1841-07-29 / HPHC-PRESS-1841-0729"],
            ["1841-07-29 (asserted)", "Q-3 states that Poe examined the cave after the recovery. The date and authorship are unverified.", "claim", "Q-3 / TC-2026-014"],
            ["1842-06-04", "Poe describes a completed parallel analysis relocating the Rogers case to Paris.", "historical", "S-01 / LTR-136 / ER-WEB-26-031"],
            ["1842-11 to 1843-02", "The three installments of The Mystery of Marie Roget appear in Ladies' Companion.", "historical", "S-02a-c / ER-WEB-26-032–034"],
            ["2026-02-11 20:20", "Ada Bell photographs TEMP-L2026.002.001 in preview case 3; Q-3 is attached to clipping Q-3B.", "observed", "IMG-221 / frame 04"],
            ["2026-02-11 20:31", "Credential CRANE-04 is recorded at the pump corridor; the event does not identify the person using it.", "system", "access export AX-8814"],
            ["2026-02-11 20:38", "The Quill device account receives an interrupted voicemail naming the pump housing; MER-26-19 does not identify the speaker.", "device", "device report MER-26-19"],
            ["2026-02-11 21:10", "Missing-person protocol begins.", "observed", "incident log IR-26-07"],
        ],
        "source_notes": [
            ["H-01", "New York Herald, 29 July 1841, clipping file HPHC-PRESS-1841-0729; event date only"],
            ["S-01", "Poe to George Roberts, 4 June 1842, LTR-136; E. A. Poe Society transcription"],
            ["S-02a-c", "Ladies' Companion 17 (Nov.–Dec. 1842) and 18 (Feb. 1843); three-part first publication"],
            ["Q-3", "Questioned note in TEMP-L2026.002.001; examination report ATCL-26-00387 addresses manufacture, not authorship"],
        ],
        "conclusion": "This chronology does not verify Q-3's asserted 29 July 1841 date or authorship. The historical sources document the Rogers recovery, Poe's June 1842 account of his method, and later publication. Preview-night entries establish only the recorded observation, credential event, device record, or incident action stated in each row.",
    },
    "conservation_examination": {
        "organization": "Alder Trace Conservation Laboratory",
        "department": "Paper & Trace Materials",
        "record_id": "ATCL-26-00387",
        "represented_date": "2026-02-11",
        "exported_at": "2026-02-11 18:46:00-05:00",
        "case_reference": "HPHC ER-2026-02 / TC-2026-014 / Q-3",
        "laboratory_address": "221 Mercer Street, Suite 410 · Jersey City, NJ 07302",
        "quality_system": "Case file 26-00387 · report issue 1",
        "examiner": "Morgan Voss, paper conservator",
        "technical_reviewer": "Leena Park, senior materials examiner",
        "custody_events": [
            ["2026-02-10 15:42 ET", "Ada Bell / HPHC", "Morgan Voss / ATCL", "TC-2026-014; sleeve seal 0412 intact"],
            ["2026-02-11 08:35 ET", "Morgan Voss", "ATCL bench P-04", "Seal 0412 opened; items photographed as IMG-387-01–03"],
            ["2026-02-11 18:38 ET", "Morgan Voss / ATCL", "Ada Bell / HPHC", "CE-387-06; returned to sleeve 0412; seal 0421 applied"],
        ],
        "items": [
            ["Q-3A", "Questioned note; handwriting-like black line on stained paper", "received in sleeve under seal 0412"],
            ["Q-3B", "Attached printed clipping fragment", "same sleeve; attachment not separated"],
        ],
        "derived_samples": [
            ["C-1", "Black particulate lifted from the questioned line on Q-3A after IMG-387-04", "glassine fold / seal 0417"],
            ["F-1", "Fiber teased from Q-3A surface after in-situ imaging", "glass slide / mount 26-387-F1"],
        ],
        "methods": [
            ["VIS", "stereo visual examination, 10x-40x", "ATCL-MIC-04 / CAL-26-0201", "IMG-387-01–08 / MEAS-387-01", "non-destructive"],
            ["UV", "long-wave ultraviolet examination", "ATCL-UV-02 / 365 nm", "IMG-387-09–12", "non-destructive"],
            ["FTIR-ATR", "binder screening on particulate C-1", "ATCL-FTIR-01", "FTIR-387-C1-01", "C-1 consumed"],
            ["FIB", "transmitted-light morphology of fiber F-1", "ATCL-CMP-03", "IMG-387-F1-01–04", "mount retained"],
            ["PAP", "transmitted-light paper survey of Q-3B in situ", "ATCL-CMP-03", "IMG-387-Q3B-01–03", "non-destructive"],
        ],
        "observations": [
            "MEAS-387-01 records fused, rounded particles from the questioned line, 18–42 µm across after calibration check CAL-26-0201; IMG-387-04–08 show edge gloss and satellite particles. This morphology is not characteristic of an ink line or letterpress impression.",
            "IMG-387-09–12 show the black line crossing a fluorescent stain boundary without diffusion into it. The line material lies above the dried boundary.",
            "FTIR-387-C1-01 records styrene-acrylate binder bands consistent with the laboratory toner reference ATCL-REF-TNR-07. Optical examination records the particulate as opaque black; FTIR does not identify carbon black. The combined result is a class association, not printer-source identification.",
            "Without separating the attachment, transmitted light was introduced at Q-3B's exposed lower edge and images IMG-387-Q3B-01–03 were recorded in situ. They show laid rag-fiber paper features. IMG-387-F1-01–04 separately show a bright trilobal manufactured fiber from Q-3A; neither observation dates an item.",
        ],
        "results": [
            ["IMG-387-04–08 / MEAS-387-01", "Calibrated fused-particle measurements from questioned line", "supports toner-class particulate in the line"],
            ["IMG-387-09–12", "Line above stain boundary", "supports application after the staining event"],
            ["FTIR-387-C1-01", "Styrene-acrylate binder bands", "consistent with ATCL-REF-TNR-07; class level"],
            ["IMG-387-F1-01–04", "Trilobal manufactured fiber morphology", "class characteristic only"],
            ["IMG-387-Q3B-01–03", "In-situ survey: laid rag-fiber paper features in Q-3B", "paper description only; no date inference"],
        ],
        "output_disposition": [
            ["IMG-387-01–12 / MEAS-387-01", "case image store / ATCL-26-00387", "retained"],
            ["FTIR-387-C1-01", "spectral store / ATCL-26-00387", "digital spectrum retained; physical C-1 consumed"],
            ["IMG-387-F1-01–04", "case image store / sample F-1", "retained"],
            ["IMG-387-Q3B-01–03", "case image store / item Q-3B", "retained"],
        ],
        "conclusion": "The questioned line on Q-3A contains fused particulate with a styrene-acrylate spectrum consistent with the laboratory toner reference. Its position above the fluorescent stain boundary supports application after that staining event. The separate transmitted-light survey records laid rag-fiber features in Q-3B only. These examinations do not establish an overall manufacture date, a common-manufacture history, or the identity of a printer, author, or source.",
        "limitations": "Class characteristics cannot identify a unique printer, person, or source. The findings are class-level associations. No destructive paper dating, ink dating, printer-source comparison, or authorship examination was authorized. Q-3B was not separated from Q-3A. The conclusion applies only to the received items, derived samples, and outputs listed.",
    },
    "access_event_report": {
        "organization": "Hudson Palisade History Center",
        "system": "Northstar Access Control 8.4",
        "record_id": "AX-8814",
        "represented_date": "2026-02-11",
        "exported_at": "2026-02-11 21:14:00-05:00",
        "report_name": "Historical Event Report",
        "site": "HPHC-01 / Hudson Palisade History Center",
        "controller": "CTRL-LC-02 / lower cave",
        "database": "ACS-HIST-01",
        "operator": "NR-17 / Nora Reyes",
        "workstation": "SEC-WS-03",
        "period": "2026-02-11 20:15:00–21:12:00 EST",
        "filter": "Partition LOWER-CAVE · controller CTRL-LC-02 · access, door, REX, and system events · priorities 0–255",
        "events": [
            ["384760", "20:16:09", "—", "—", "PUMP-COR / exterior", "Door secure", "STATE"],
            ["384762", "20:17:44", "—", "—", "SERVICE-RECESS", "Door closed", "STATE"],
            ["384766", "20:20:01", "—", "—", "CTRL-LC-02", "Scheduled poll complete", "SYSTEM"],
            ["384771", "20:24:03", "QUILL-01", "Miriam Quill", "PUMP-COR / exterior", "Access granted", "ENTRY"],
            ["384773", "20:24:09", "—", "—", "PUMP-COR / exterior", "Door opened", "STATE"],
            ["384775", "20:24:17", "—", "—", "PUMP-COR / exterior", "Door closed", "STATE"],
            ["384779", "20:31:16", "CRANE-04", "Elias Crane", "PUMP-COR / exterior", "Access granted", "ENTRY"],
            ["384781", "20:31:22", "—", "—", "PUMP-COR / exterior", "Door opened", "STATE"],
            ["384783", "20:31:31", "—", "—", "PUMP-COR / exterior", "Door closed", "STATE"],
            ["384786", "20:36:42", "QUILL-01", "Miriam Quill", "SERVICE-RECESS", "Access granted", "OPEN"],
            ["384788", "20:36:47", "—", "—", "SERVICE-RECESS", "Door opened", "STATE"],
            ["384790", "20:37:02", "—", "—", "SERVICE-RECESS", "Door closed", "STATE"],
            ["384791", "20:43:08", "CRANE-04", "Elias Crane", "PUMP-COR / interior REX", "Request-to-exit", "EXIT"],
            ["384793", "20:43:11", "—", "—", "PUMP-COR / exterior", "Door opened", "STATE"],
            ["384795", "20:43:19", "—", "—", "PUMP-COR / exterior", "Door closed", "STATE"],
            ["384804", "20:50:00", "—", "—", "CTRL-LC-02", "Scheduled poll complete", "SYSTEM"],
            ["384812", "21:00:00", "—", "—", "CTRL-LC-02", "Scheduled poll complete", "SYSTEM"],
            ["384818", "21:10:00", "—", "—", "CTRL-LC-02", "Scheduled poll complete", "SYSTEM"],
            ["384820", "21:10:47", "—", "—", "PUMP-COR / exterior", "Door secure", "STATE"],
            ["384822", "21:11:03", "—", "—", "SERVICE-RECESS", "Door closed", "STATE"],
        ],
        "integrity_note": "Events retrieved from ACS-HIST-01 in controller sequence. Cardholder text is the database label stored for the credential at event time.",
    },
    "tenant_account_ledger": {
        "organization": "Riverglass Residential Management, LLC",
        "system": "HarborLedger Property Management 11.6",
        "record_id": "TA-4C-2026-02-11",
        "represented_date": "2026-02-11",
        "exported_at": "2026-02-11 21:22:00-05:00",
        "portfolio": "03 / Hudson County",
        "property_code": "LOOM-047",
        "operator": "JP-04 / account services",
        "report_period": "2025-12-18 through 2026-02-11",
        "property": "Loom House",
        "street": "47 Loomwright Mews",
        "unit": "4C",
        "municipality": "Hoboken",
        "state": "NJ",
        "zip": "07030",
        "tenant": "Elias Crane",
        "account_number": "LM-004C-26",
        "term_start": "2026-01-01",
        "term_end": "2026-12-31",
        "monthly_rent": 2800,
        "deposit": 4200,
        "deposit_received": "2025-12-18",
        "deposit_reference": "SD-LM-004C",
        "occupancy_status": "ACTIVE",
        "transactions": [
            ["2025-12-18", "OPEN", "MIG-0001", "Opening balances", "—", "—", "$0.00", "$0.00"],
            ["2025-12-18", "DEP", "DEP-1218-04", "Security deposit receipt", "—", "$4,200.00", "$0.00", "$4,200.00"],
            ["2026-01-01", "RNT", "JAN-2026", "January rent", "$2,800.00", "—", "$2,800.00", "$4,200.00"],
            ["2026-01-02", "ACH", "98114", "ACH rent receipt", "—", "$2,800.00", "$0.00", "$4,200.00"],
            ["2026-02-01", "RNT", "FEB-2026", "February rent", "$2,800.00", "—", "$2,800.00", "$4,200.00"],
            ["2026-02-03", "ACH", "99402", "ACH rent receipt", "—", "$2,800.00", "$0.00", "$4,200.00"],
        ],
    },
    "voicemail_evidence_report": {
        "organization": "Hudson Palisade History Center",
        "department": "Incident Review",
        "record_id": "MER-26-019",
        "form_number": "DV-04",
        "form_revision": "Rev. 2 / effective 2025-10-01",
        "issuing_unit": "Records and Digital Evidence Coordination",
        "record_series": "HPHC-IR-04 / incident evidence collection worksheets",
        "retention_rule": "Close of incident review + 7 years",
        "case_system": "CaseTrack 4.8 / case IR-26-07 / item MER-26-019",
        "case_export_job": "CT-20260211-2131-07",
        "review_entry": "DR-2026-219 / user dchen / 2026-02-11 21:28 EST",
        "represented_date": "2026-02-11",
        "exported_at": "2026-02-11 21:31:00-05:00",
        "device": "Apple iPhone 14 / evidence item IR-26-07-D02 (Elias Crane)",
        "device_model": "Apple iPhone 14 / A2649",
        "device_identifier": "serial ending H7Q9 / line ending 0196",
        "device_os": "iOS 18.3.1 (22D72)",
        "device_state": "Powered on; unlocked by owner; network state unchanged",
        "account": "recipient device line ending 0196",
        "from_name": "Miriam Quill / line ending 0148",
        "to_name": "Elias Crane",
        "received_at": "2026-02-11 20:38:14 EST",
        "duration": "00:00:19",
        "message_id": "VM-00018472",
        "source_application": "iOS Phone / Visual Voicemail",
        "source_filename": "VM-00018472_20260211T203814-0500.m4a",
        "audio_bytes": "318,442 bytes",
        "audio_hash": "SHA-256 90e48896 7b312d08 f16e4bda 6fc2a84c 6eea4c3d 9d61ea29 a3bd953a 711fc12a",
        "repository_locator": "IR-26-07/source/MER-26-019/VM-00018472.m4a",
        "collection_scope": "Owner-consented export of message VM-00018472 only; no device extraction",
        "collection_authority": "Elias Crane written consent / IR-26-07 intake sheet 02",
        "collection_method": "Phone > Voicemail > Share > Save to Files; AirDrop to controlled intake workstation",
        "workstation": "HPHC-IR-WKS-03 / macOS 15.3.1 / operator account nreyes",
        "staging_path": "/Users/Shared/IR-26-07/intake/VM-00018472_20260211T203814-0500.m4a",
        "evidence_path": "/Volumes/CASE-IR-26-07/source/MER-26-019/VM-00018472.m4a",
        "hash_tool": "/usr/bin/shasum 6.02, option -a 256",
        "hash_first": "21:19:53 EST / staging path / 90e488967b312d08f16e4bda6fc2a84c6eea4c3d9d61ea29a3bd953a711fc12a",
        "hash_second": "21:20:08 EST / evidence path / 90e488967b312d08f16e4bda6fc2a84c6eea4c3d9d61ea29a3bd953a711fc12a",
        "preservation": "CASE-IR-26-07 write session closed 21:20:19 EST; volume remounted read-only for review",
        "acquisition_events": [
            ["21:16:22", "IR-26-07-D02", "Owner unlocked device; operator opened Phone > Voicemail > VM-00018472"],
            ["21:17:03", "IR-26-07-D02", "Share > Save to Files; saved M4A without playback or trimming"],
            ["21:18:31", "HPHC-IR-WKS-03", "Received by AirDrop into controlled IR-26-07 intake directory"],
            ["21:19:53", "HPHC-IR-WKS-03", "Recorded size and SHA-256 at staging path"],
            ["21:20:08", "CASE-IR-26-07", "Copied to evidence path; second SHA-256 matched staging value"],
            ["21:20:19", "CASE-IR-26-07", "Closed write session; remounted case volume read-only"],
        ],
        "prepared_by": "Nora Reyes, incident records specialist",
        "reviewed_by": "David Chen, digital evidence coordinator",
        "prepared_at": "2026-02-11 21:26 EST",
        "reviewed_at": "2026-02-11 21:28 EST",
        "transcription_method": "Manual listening at 1.0x from read-only evidence path; no filtering or enhancement",
        "segments": [
            ["00:00.0", "Elias, the proof cannot survive either test. The visit never happened, and Morgan found—", "speech; clipped ending"],
            ["00:08.1", "[metal latch; low mechanical vibration]", "non-speech sound"],
            ["00:12.7", "Behind the pump housing. He has shut the—", "speech; connection loss"],
            ["00:18.9", "[recording stops]", "cause not determined from export"],
        ],
        "limitations": "This was a limited owner-consented message export, not a forensic image or full device extraction. The transcript is an analyst-prepared listening aid and may contain hearing or punctuation errors. The retained M4A export is the source for this transcript; it is not a carrier-origin record. Caller labels reproduce device account data and are not biometric speaker identification.",
    },
    "pump_emergency_card": {
        "organization": "Hudson Palisade History Center",
        "department": "Facilities Operations",
        "record_id": "EIC-04",
        "represented_date": "2025-09-22",
        "issued_date": "2025-09-18",
        "exported_at": "2025-09-18 16:10:00-04:00",
        "equipment": "Pump P-2 / service recess R-2",
        "equipment_ids": "P-2 · DR-2 · ER-2 · ES-2 · DS-2",
        "location": "Lower Cave Service Corridor / east wall",
        "revision": "Rev. 4 / effective 2025-09-22",
        "prepared_by": "Facilities Operations, Hudson Palisade History Center",
        "owner": "Owner: Facilities Operations Manager / ext. 225",
        "approved_by": "Approved: M. Torres, Director of Safety & Compliance / 2025-09-17",
        "approval_record": "FAC-APR-250917-04",
        "supersedes": "EIC-04 Rev. 3 / 2024-06-06",
        "classification": "DMS STATUS: RELEASED",
        "source_record": "Facilities DMS / document EIC-04 / revision 04",
        "print_control": "Posted print FAC-EIC04-R4-P01 / generated 2025-09-18 16:10 EDT",
        "scenario": "USE WHEN A PERSON IN RECESS R-2 CANNOT OPEN DOOR DR-2 OR RESPONDERS REPORT A JAMMED LATCH.",
        "warning": "DANGER — PERMIT-REQUIRED CONFINED SPACE. DO NOT ENTER FOR RESCUE. R-2 IS NOT DESIGNED FOR CONTINUOUS OCCUPANCY.",
        "release_description": "ER-2 is the red ring beneath the red lift cover on the corridor side of P-2. It releases latch DR-2 without crossing the R-2 threshold or reaching inside the P-2 guard.",
        "steps": [
            "Call Site Emergency Control, ext. 222. Report ‘R-2 trapped person,’ number and condition if known, and the permit number and attendant if present. Under CSP-03, Control calls 911 and requests Hoboken Fire Department technical rescue.",
            "Stay in the corridor. Press emergency stop ES-2 and confirm P-2 motion and operating sound stop. ES-2 is an emergency stop, not energy isolation.",
            "Lift the red ER-2 cover and pull the RED RELEASE RING fully outward. Do not cross the R-2 threshold or reach inside the P-2 guard.",
            "Confirm DR-2 unlatches. Block it fully open. Direct an ambulatory person to self-exit. If no self-exit, wait for technical rescue—DO NOT ENTER. Barricade P-2/R-2 and keep P-2 stopped.",
        ],
        "loto_boundary": "ER-2 is an external, non-entry release. This card does not authorize entry, guard access, latch repair, or servicing. Trained and authorized staff must use CSP-03 and ECP-LOTO-02 in full.",
        "release_failure": "If one full pull of ER-2 does not unlatch DR-2: STOP. Do not pry the door, defeat the latch, remove the guard, or attempt entry. Tell Site Emergency Control ‘ER-2 failed’ and wait for the designated rescue service.",
        "prohibitions": "DO NOT enter R-2 for rescue · DO NOT reach past the P-2 guard · DO NOT treat ES-2 as lockout · DO NOT remove another employee’s lock or tag · After ER-2 has been operated, DO NOT restart P-2 unless the Facilities Operations Supervisor authorizes return under ECP-LOTO-02",
        "communications": "SITE EMERGENCY CONTROL: extension 222 / radio channel FAC-1 · EXTERNAL EMERGENCY: 911 · Equipment location to report: Lower Cave Service Corridor, east wall, P-2 / R-2",
        "restoration": "KEEP P-2 STOPPED. The Facilities Operations Supervisor may release it only after rescue clearance, headcount, and documented P-2/DR-2/ER-2 inspection. Any LOTO removal follows ECP-LOTO-02.",
        "records": "Site Control opens an emergency log. Facilities opens a MaintainCMMS work order for P-2 using event code ER-2 and records inspection, repair, and supervisor restoration approval.",
        "procedures": "EAP-01 Emergency Action Plan · CSP-03 Permit-Space Entry and Rescue · ECP-LOTO-02 Hazardous Energy Control · PM-P2-06 Release Inspection",
        "posting_control": "POST ONLY ON EAST WALL ADJACENT TO ER-2 · verify revision against MaintainCMMS before replacement",
        "inspection": "MONTHLY FIELD CHECK — PM-P2-06 log · date __________ · initials ______",
    },
}


def _validate_kind(kind: str) -> None:
    if kind not in DEFAULTS:
        raise KeyError(f"unknown investigation artifact kind: {kind}")


def sample_artifact(
    rng: random.Random,
    *,
    kind: str,
    pins: dict | None = None,
    canon: dict | None = None,
) -> dict[str, Any]:
    """Build one canonical record from caller facts; no derived fact is sampled."""
    _validate_kind(kind)
    model = deepcopy(DEFAULTS[kind])
    model.update(deepcopy(canon or {}))
    model.update(deepcopy(pins or {}))
    model["kind"] = kind
    # Stable, producing-system detail; it never changes a caller-owned fact.
    model["export_job"] = f"{rng.randrange(1_000_000):06d}"
    return model


def export_created(model: dict[str, Any]) -> str:
    return str(model["exported_at"])


def _display_model(model: dict[str, Any], defect: dict | None) -> dict[str, Any]:
    shown = deepcopy(model)
    if not defect:
        return shown
    if set(defect) != {"field", "value"}:
        raise ValueError("investigation defect requires exactly field and value")
    field = defect["field"]
    if not isinstance(field, str) or field not in shown:
        raise ValueError("investigation defect field must name one displayed scalar")
    if isinstance(shown[field], (list, dict)):
        raise ValueError("investigation defect may alter only one displayed scalar")
    shown[field] = defect["value"]
    return shown


def public_display_facts(
    model: dict[str, Any], *, defect: dict | None = None
) -> dict[str, Any]:
    shown = _display_model(model, defect)
    return {
        "document_class": shown["kind"],
        "record_id": shown["record_id"],
        "represented_date": shown["represented_date"],
        "reading_copy": _reading_copy(shown),
        "accessibility": {
            "required": True,
            "source": "embedded PDF text layer",
            "interpretation": [],
        },
    }


_BASE = getSampleStyleSheet()
BODY = ParagraphStyle(
    "InvestigationBody", parent=_BASE["BodyText"], fontName="Helvetica",
    fontSize=9.2, leading=12.2, textColor=colors.HexColor("#1f2933"),
    spaceAfter=6,
)
SMALL = ParagraphStyle(
    "InvestigationSmall", parent=BODY, fontSize=7.6, leading=9.4,
    textColor=colors.HexColor("#485563"),
)
H1 = ParagraphStyle(
    "InvestigationH1", parent=_BASE["Title"], fontName="Helvetica-Bold",
    fontSize=17, leading=20, alignment=TA_LEFT,
    textColor=colors.HexColor("#172b3a"), spaceAfter=8,
)
H2 = ParagraphStyle(
    "InvestigationH2", parent=_BASE["Heading2"], fontName="Helvetica-Bold",
    fontSize=9, leading=11, textTransform="uppercase", tracking=0.7,
    textColor=colors.HexColor("#28566f"), spaceBefore=10, spaceAfter=5,
)
MONO = ParagraphStyle(
    "InvestigationMono", parent=SMALL, fontName="Courier", fontSize=7.1,
    leading=8.7,
)
TABLE_HEADER = ParagraphStyle(
    "InvestigationTableHeader", parent=SMALL, fontName="Helvetica-Bold",
    textColor=colors.white,
)


def _escape(value: Any) -> str:
    return (str(value).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;"))


def _p(value: Any, style: ParagraphStyle = BODY) -> Paragraph:
    return Paragraph(_escape(value), style)


def _table(
    rows: list[list[Any]], widths: list[float], *, header: bool = True,
    font_size: float = 7.6,
) -> Table:
    cells = [
        [
            _p(value, TABLE_HEADER if header and row_index == 0 else SMALL)
            for value in row
        ]
        for row_index, row in enumerate(rows)
    ]
    table = Table(cells, colWidths=widths, repeatRows=1 if header else 0)
    commands = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#9aa7b1")),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("FONTSIZE", (0, 0), (-1, -1), font_size),
        ("ROWBACKGROUNDS", (0, 1 if header else 0), (-1, -1),
         [colors.white, colors.HexColor("#f3f6f7")]),
    ]
    if header:
        commands.extend([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#173f56")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ])
    table.setStyle(TableStyle(commands))
    return table


DOCUMENT_TITLES = {
    "museum_research_note": "Collections research note",
    "curatorial_chronology": "Curatorial chronology",
    "conservation_examination": "Limited examination report",
    "access_event_report": "Historical access event report",
    "tenant_account_ledger": "Tenant account record",
    "voicemail_evidence_report": "Limited mobile evidence collection worksheet",
    "pump_emergency_card": "Emergency release instruction card",
}


def _document_title(model: dict[str, Any]) -> str:
    return str(
        model.get("title")
        or model.get("report_name")
        or DOCUMENT_TITLES[model["kind"]]
    )


def _document_author(model: dict[str, Any]) -> str:
    return str(
        model.get("prepared_by")
        or model.get("examiner")
        or model["organization"]
    )


def _document_subject(model: dict[str, Any]) -> str:
    return str(
        model.get("subject")
        or model.get("case_reference")
        or f"{DOCUMENT_TITLES[model['kind']]} {model['record_id']}"
    )


def _ensure_office_fonts() -> None:
    """Register ReportLab's redistributable embedded office-style family."""
    try:
        pdfmetrics.getFont("VeraOffice")
    except KeyError:
        pdfmetrics.registerFont(TTFont("VeraOffice", "Vera.ttf"))
        pdfmetrics.registerFont(TTFont("VeraOffice-Bold", "VeraBd.ttf"))
        pdfmetrics.registerFont(TTFont("VeraOffice-Italic", "VeraIt.ttf"))
        pdfmetrics.registerFontFamily(
            "VeraOffice",
            normal="VeraOffice",
            bold="VeraOffice-Bold",
            italic="VeraOffice-Italic",
            boldItalic="VeraOffice-Bold",
        )


def _footer_callback(model: dict[str, Any], metadata: dict[str, Any]):
    def draw(c: canvas.Canvas, doc) -> None:
        c.saveState()
        c.setCreator(metadata["creator"])
        c.setProducer(metadata["producer"])
        c.setTitle(_document_title(model))
        c.setAuthor(_document_author(model))
        c.setSubject(_document_subject(model))
        c.setStrokeColor(colors.HexColor("#aab4bc"))
        c.line(doc.leftMargin, 0.52 * inch, doc.pagesize[0] - doc.rightMargin, 0.52 * inch)
        c.setFillColor(colors.HexColor("#596875"))
        c.setFont("Helvetica", 7)
        c.drawString(doc.leftMargin, 0.37 * inch, str(model["record_id"]))
        c.drawCentredString(doc.pagesize[0] / 2, 0.37 * inch,
                            f"RECORD DATE · {model['represented_date']}")
        c.drawRightString(doc.pagesize[0] - doc.rightMargin, 0.37 * inch,
                          f"Page {doc.page}")
        c.restoreState()
    return draw


def _memo_footer_callback(model: dict[str, Any], metadata: dict[str, Any]):
    def draw(c: canvas.Canvas, doc) -> None:
        c.saveState()
        c.setCreator(metadata["creator"])
        c.setProducer(metadata["producer"])
        c.setTitle(_document_title(model))
        c.setAuthor(_document_author(model))
        c.setSubject(_document_subject(model))
        c.setStrokeColor(colors.HexColor("#858585"))
        c.line(doc.leftMargin, 0.52 * inch,
               doc.pagesize[0] - doc.rightMargin, 0.52 * inch)
        c.setFillColor(colors.HexColor("#555555"))
        _ensure_office_fonts()
        c.setFont("VeraOffice", 7.5)
        if doc.page > 1:
            c.setFillColor(colors.HexColor("#666666"))
            c.drawString(
                doc.leftMargin,
                doc.pagesize[1] - 0.34 * inch,
                f"{model['record_id']} · RESEARCH NOTE · continued",
            )
            c.setStrokeColor(colors.HexColor("#b0b0b0"))
            c.line(
                doc.leftMargin,
                doc.pagesize[1] - 0.43 * inch,
                doc.pagesize[0] - doc.rightMargin,
                doc.pagesize[1] - 0.43 * inch,
            )
            c.setFillColor(colors.HexColor("#555555"))
        c.drawString(doc.leftMargin, 0.35 * inch, str(model["record_id"]))
        c.drawRightString(doc.pagesize[0] - doc.rightMargin, 0.35 * inch,
                          f"Page {doc.page}")
        c.restoreState()
    return draw


def _lab_footer_callback(model: dict[str, Any], metadata: dict[str, Any]):
    def draw(c: canvas.Canvas, doc) -> None:
        c.saveState()
        c.setCreator(metadata["creator"])
        c.setProducer(metadata["producer"])
        c.setTitle(_document_title(model))
        c.setAuthor(_document_author(model))
        c.setSubject(_document_subject(model))
        _ensure_office_fonts()
        c.setStrokeColor(colors.HexColor("#777777"))
        c.line(doc.leftMargin, 0.50 * inch,
               doc.pagesize[0] - doc.rightMargin, 0.50 * inch)
        c.setFillColor(colors.HexColor("#555555"))
        c.setFont("VeraOffice", 7)
        c.drawString(doc.leftMargin, 0.34 * inch, str(model["record_id"]))
        c.drawCentredString(doc.pagesize[0] / 2, 0.34 * inch,
                            str(model["department"]))
        c.drawRightString(doc.pagesize[0] - doc.rightMargin, 0.34 * inch,
                          f"Page {doc.page}")
        if doc.page > 1:
            c.setFont("VeraOffice", 7)
            c.drawRightString(doc.pagesize[0] - doc.rightMargin,
                              doc.pagesize[1] - 0.34 * inch,
                              f"{model['record_id']} · continued")
        c.restoreState()
    return draw


def _mobile_footer_callback(model: dict[str, Any], metadata: dict[str, Any]):
    def draw(c: canvas.Canvas, doc) -> None:
        c.saveState()
        c.setCreator(metadata["creator"])
        c.setProducer(metadata["producer"])
        c.setTitle(_document_title(model))
        c.setAuthor(_document_author(model))
        c.setSubject(_document_subject(model))
        _ensure_office_fonts()
        c.setStrokeColor(colors.HexColor("#777777"))
        c.line(doc.leftMargin, 0.50 * inch,
               doc.pagesize[0] - doc.rightMargin, 0.50 * inch)
        c.setFillColor(colors.HexColor("#555555"))
        c.setFont("VeraOffice", 7)
        c.drawString(doc.leftMargin, 0.34 * inch, str(model["record_id"]))
        c.drawCentredString(doc.pagesize[0] / 2, 0.34 * inch,
                            f"{model['form_number']} {model['form_revision']} · {model['record_series'].split(' / ')[0]}")
        c.drawRightString(doc.pagesize[0] - doc.rightMargin, 0.34 * inch,
                          f"Page {doc.page} of 2")
        if doc.page > 1:
            c.setFillColor(colors.HexColor("#666666"))
            c.drawString(doc.leftMargin, doc.pagesize[1] - 0.34 * inch,
                         f"IR-26-07 / {model['record_id']} · {model['form_number']} continued")
            c.setStrokeColor(colors.HexColor("#b0b0b0"))
            c.line(doc.leftMargin, doc.pagesize[1] - 0.43 * inch,
                   doc.pagesize[0] - doc.rightMargin,
                   doc.pagesize[1] - 0.43 * inch)
        c.restoreState()
    return draw


def _tenant_footer_callback(model: dict[str, Any], metadata: dict[str, Any]):
    def draw(c: canvas.Canvas, doc) -> None:
        c.saveState()
        c.setCreator(metadata["creator"])
        c.setProducer(metadata["producer"])
        c.setTitle(_document_title(model))
        c.setAuthor(_document_author(model))
        c.setSubject(_document_subject(model))
        _ensure_office_fonts()
        c.setStrokeColor(colors.HexColor("#777777"))
        c.line(doc.leftMargin, 0.50 * inch,
               doc.pagesize[0] - doc.rightMargin, 0.50 * inch)
        c.setFillColor(colors.HexColor("#555555"))
        c.setFont("VeraOffice", 7)
        c.drawString(doc.leftMargin, 0.34 * inch, str(model["record_id"]))
        c.drawCentredString(doc.pagesize[0] / 2, 0.34 * inch,
                            "HarborLedger 11.6 · Resident Ledger")
        c.drawRightString(doc.pagesize[0] - doc.rightMargin, 0.34 * inch,
                          "Page 1 of 1")
        c.restoreState()
    return draw


def _finalize(raw: bytes, metadata: dict[str, Any]) -> bytes:
    fixed = legalpdf._fix_dates(
        raw, created=metadata.get("created"), modified=metadata.get("modified")
    )
    return legalpdf._fix_id(fixed)


def _document(
    model: dict[str, Any], metadata: dict[str, Any], story: list[Any], *,
    pagesize=letter, margins=(0.7, 0.7, 0.7, 0.72), footer_factory=None,
) -> bytes:
    target = io.BytesIO()
    left, right, top, bottom = (item * inch for item in margins)
    doc = SimpleDocTemplate(
        target, pagesize=pagesize, leftMargin=left, rightMargin=right,
        topMargin=top, bottomMargin=bottom,
        title=_document_title(model),
    )
    callback = (footer_factory or _footer_callback)(model, metadata)
    doc.build(
        story, onFirstPage=callback, onLaterPages=callback,
        canvasmaker=partial(canvas.Canvas, invariant=1),
    )
    return _finalize(target.getvalue(), metadata)


def _masthead(model: dict[str, Any], kicker: str) -> list[Any]:
    return [
        _p(model["organization"], ParagraphStyle(
            "Org", parent=SMALL, fontName="Helvetica-Bold", fontSize=8.5,
            leading=10, textColor=colors.HexColor("#28566f"),
        )),
        _p(kicker, ParagraphStyle(
            "Kicker", parent=SMALL, fontSize=7.4, leading=9,
            textColor=colors.HexColor("#6f7b84"),
        )),
        Spacer(1, 8),
    ]


def _render_research(model: dict[str, Any], metadata: dict[str, Any]) -> bytes:
    _ensure_office_fonts()
    memo_body = ParagraphStyle(
        "ResearchMemoBody", parent=BODY, fontName="VeraOffice",
        fontSize=10.2, leading=12.8, textColor=colors.black, spaceAfter=6,
    )
    memo_small = ParagraphStyle(
        "ResearchMemoSmall", parent=memo_body, fontSize=8.9, leading=11,
        textColor=colors.HexColor("#333333"),
    )
    memo_heading = ParagraphStyle(
        "ResearchMemoHeading", parent=memo_body, fontName="VeraOffice-Bold",
        fontSize=10.2, leading=12.8, spaceBefore=8, spaceAfter=4,
    )
    memo_title = ParagraphStyle(
        "ResearchMemoTitle", parent=memo_body, fontName="VeraOffice-Bold",
        fontSize=14, leading=17, spaceAfter=9,
    )
    label = ParagraphStyle(
        "ResearchMemoLabel", parent=memo_small, fontName="VeraOffice-Bold",
        fontSize=8.9,
    )
    header_rows = [
        [_p("TO", label), _p(model["reviewed_by"], memo_small)],
        [_p("FROM", label), _p(model["prepared_by"], memo_small)],
        [_p("DATE", label), _p(model["represented_date"], memo_small)],
        [_p("FILE", label), _p(f"{model['records_series']} · {model['record_id']}", memo_small)],
        [_p("STATUS", label), _p("FINAL", memo_small)],
        [_p("REVIEW", label), _p(
            f"{model['reviewed_by']} — {model['reviewed_at']}", memo_small,
        )],
        [_p("SUBJECT", label), _p(model["subject"], memo_small)],
        [_p("OBJECT REF.", label), _p(
            f"Unaccessioned lender packet {model['object_id']}, received under "
            f"{model['receipt_id']}; questioned handwriting is item Q-3 in "
            "examination report ATCL-26-00387.",
            memo_small,
        )],
        [_p("RELATED", label), _p(
            "TC-2026-014 temporary-custody record; ATCL-26-00387 conservation "
            "examination; CHR-26-017 curatorial chronology.",
            memo_small,
        )],
    ]
    header = Table(header_rows, colWidths=[0.9*inch, 5.7*inch])
    header.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
        ("TOPPADDING", (0, 0), (-1, -1), 1),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LINEBELOW", (0, -1), (-1, -1), 0.6, colors.HexColor("#666666")),
    ]))
    story = [
        _p(model["organization"], ParagraphStyle(
            "MemoOrg", parent=memo_body, fontName="VeraOffice-Bold",
            fontSize=10.5, leading=12.5, spaceAfter=1,
        )),
        _p(f"{model['department']} · {model['organization_address']}", memo_small),
        Spacer(1, 7),
        _p("RESEARCH NOTE", memo_title),
        header,
        _p("Question", memo_heading),
        _p(model["question"], memo_body),
        _p("Conclusion and scope", memo_heading),
        _p(model["finding"], memo_body),
        _p("Sources reviewed", memo_heading),
    ]
    for ref, source, use in model["sources"]:
        story.append(_p(f"{ref}  {source}. {use}.", memo_small))
    story += [
        PageBreak(),
        _p("Captured-source register", memo_heading),
        *[_p(locator, memo_small) for locator in model["source_locators"]],
        _p("Method", memo_heading),
        _p(
            "S-01 was read as a scholarly transcription of a contemporary letter. "
            "The three parts of S-02 were compared with the revised S-03 text; S-04 "
            "was used only for publication and manuscript history. The captured PDFs "
            "in ER-2026-02/web-captures were searched for Hoboken, cave, visit, New "
            "York, newspaper, and press. Every hit was read in context. The capture "
            "register preserves the consulted rendering; this was documentary "
            "research only; Q-3 was not examined.",
            memo_body,
        ),
        _p("Research notes", memo_heading),
        *[
            _p(f"{at} — {source} — {action}", memo_small)
            for at, source, action in model["research_log"]
        ],
        _p("Discussion", memo_heading),
        _p(
            "In S-01 Poe describes the tale as a parallel Paris narrative based on "
            "the Rogers case and says, ‘I examine, each by each, the opinions and "
            "arguments of the press upon the subject.’ S-02 and S-03 likewise use "
            "newspaper files as Dupin's evidence. No searched passage supplies an "
            "affirmative first-person account of a cave visit. The narrow historical "
            "result is therefore ‘not supported by the sources reviewed,’ not "
            "‘did not happen.’",
            memo_body,
        ),
        _p("Limitations", memo_heading),
        _p(model["limitations"], memo_body),
        _p("Record action", memo_heading),
        _p(
            f"Filed by Ada Bell in {model['records_series']} on 11 February 2026. "
            f"Web captures remain with that inquiry. The lender packet remains "
            f"controlled under {model['receipt_id']}; custody and return actions are "
            "recorded there, not in this note.",
            memo_body,
        ),
    ]
    return _document(
        model, metadata, story, margins=(0.7, 0.7, 0.55, 0.58),
        footer_factory=_memo_footer_callback,
    )


def _render_chronology(model: dict[str, Any], metadata: dict[str, Any]) -> bytes:
    _ensure_office_fonts()
    sheet_body = ParagraphStyle(
        "ChronologySheetBody", parent=BODY, fontName="VeraOffice",
        fontSize=9, leading=10.8, textColor=colors.black, spaceAfter=4,
    )
    sheet_small = ParagraphStyle(
        "ChronologySheetSmall", parent=sheet_body, fontSize=8, leading=9.5,
    )
    sheet_heading = ParagraphStyle(
        "ChronologySheetHeading", parent=sheet_body,
        fontName="VeraOffice-Bold", fontSize=14, leading=17, spaceAfter=7,
    )
    chronology_cells = [
        [_p(value, ParagraphStyle(
            f"Chronology-{row_index}-{column_index}", parent=sheet_small,
            fontName=("VeraOffice-Bold" if row_index == 0 else "VeraOffice"),
            fontSize=8.4, leading=10, textColor=colors.black,
        )) for column_index, value in enumerate(row)]
        for row_index, row in enumerate(
            [["Date / time", "Event or assertion", "Source class", "Source record / locator"], *model["rows"]]
        )
    ]
    chronology = Table(
        chronology_cells,
        colWidths=[1.35 * inch, 4.55 * inch, 0.95 * inch, 2.55 * inch],
        repeatRows=1,
    )
    chronology.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#777777")),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8e8e8")),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    controls = Table([
        [_p("FILE", sheet_small), _p("ER-2026-02 / inquiry 06", sheet_small),
         _p("RECORD", sheet_small), _p(model["record_id"], sheet_small),
         _p("THROUGH", sheet_small), _p("2026-02-11 21:10 ET", sheet_small)],
        [_p("BY", sheet_small), _p(model["prepared_by"], sheet_small),
         _p("UPDATED", sheet_small), _p("2026-02-11 21:24 ET", sheet_small),
         _p("STATUS", sheet_small), _p("working", sheet_small)],
    ], colWidths=[0.65*inch, 2.65*inch, 0.75*inch, 1.45*inch, 0.75*inch, 2.55*inch])
    controls.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#888888")),
        ("FONTNAME", (0, 0), (-1, -1), "VeraOffice"),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#eeeeee")),
        ("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#eeeeee")),
        ("BACKGROUND", (4, 0), (4, -1), colors.HexColor("#eeeeee")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story = [
        _p(model["organization"], ParagraphStyle(
            "ChronologyOrg", parent=sheet_body, fontName="VeraOffice-Bold",
            fontSize=10, leading=12, spaceAfter=1,
        )),
        _p(model["department"], sheet_small),
        Spacer(1, 5),
        _p("WORKING EVENT CHRONOLOGY", sheet_heading),
        controls,
        Spacer(1, 6),
        _p(model["scope"], sheet_small),
        Spacer(1, 5),
        chronology,
        Spacer(1, 7),
        _p("ANALYST NOTE", ParagraphStyle(
            "ChronologyNoteHeading", parent=sheet_small,
            fontName="VeraOffice-Bold", spaceAfter=2,
        )),
        _p(model["conclusion"], sheet_small),
    ]
    return _document(
        model, metadata, story, pagesize=landscape(letter),
        margins=(0.65, 0.65, 0.5, 0.58),
        footer_factory=_memo_footer_callback,
    )


def _render_conservation(model: dict[str, Any], metadata: dict[str, Any]) -> bytes:
    _ensure_office_fonts()
    lab_body = ParagraphStyle(
        "LabBody", parent=BODY, fontName="VeraOffice", fontSize=8.8,
        leading=11.2, textColor=colors.black, spaceAfter=5,
    )
    lab_small = ParagraphStyle(
        "LabSmall", parent=lab_body, fontSize=8.0, leading=9.7,
        textColor=colors.HexColor("#222222"),
    )
    lab_label = ParagraphStyle(
        "LabLabel", parent=lab_small, fontName="VeraOffice-Bold",
        fontSize=7.2, leading=9,
    )
    lab_h1 = ParagraphStyle(
        "LabH1", parent=lab_body, fontName="VeraOffice-Bold", fontSize=14,
        leading=17, spaceAfter=7,
    )
    lab_h2 = ParagraphStyle(
        "LabH2", parent=lab_body, fontName="VeraOffice-Bold", fontSize=8.8,
        leading=10.5, spaceBefore=8, spaceAfter=3,
    )

    def lab_table(rows: list[list[Any]], widths: list[float], *, header: bool = True) -> Table:
        cells = [[
            _p(value, lab_label if header and row_index == 0 else lab_small)
            for value in row
        ] for row_index, row in enumerate(rows)]
        table = Table(cells, colWidths=widths, repeatRows=1 if header else 0)
        commands = [
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 2),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 2.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
            ("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.HexColor("#aaaaaa")),
        ]
        if header:
            commands.extend([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e9e9e9")),
                ("LINEABOVE", (0, 0), (-1, 0), 0.6, colors.HexColor("#555555")),
                ("LINEBELOW", (0, 0), (-1, 0), 0.6, colors.HexColor("#555555")),
            ])
        table.setStyle(TableStyle(commands))
        return table

    def signature_mark(variant: int) -> Drawing:
        drawing = Drawing(205, 25)
        mark = DrawingPath()
        if variant == 1:
            mark.moveTo(3, 6)
            mark.curveTo(8, 24, 13, 23, 14, 7)
            mark.curveTo(17, 15, 22, 18, 22, 8)
            mark.curveTo(27, 15, 31, 15, 32, 7)
            mark.curveTo(39, 14, 46, 13, 54, 8)
            mark.curveTo(67, 1, 78, 15, 91, 8)
            mark.curveTo(107, 0, 119, 13, 137, 7)
        else:
            mark.moveTo(4, 7)
            mark.curveTo(8, 23, 15, 24, 17, 7)
            mark.curveTo(24, 18, 28, 16, 30, 6)
            mark.curveTo(35, 14, 42, 17, 44, 7)
            mark.curveTo(52, 15, 61, 13, 72, 7)
            mark.curveTo(89, 0, 99, 16, 112, 7)
            mark.curveTo(128, 1, 139, 12, 155, 8)
        mark.strokeColor = colors.HexColor("#243b5a")
        mark.strokeWidth = 1.15
        mark.fillColor = None
        drawing.add(mark)
        return drawing

    header = Table([
        [_p(model["organization"], ParagraphStyle(
             "LabOrg", parent=lab_body, fontName="VeraOffice-Bold",
             fontSize=11.5, leading=13,
         )), _p("FINAL REPORT", ParagraphStyle(
             "LabStatus", parent=lab_label, alignment=2, fontSize=8,
         ))],
        [_p(model["department"], lab_small), _p(model["quality_system"], ParagraphStyle(
             "LabControl", parent=lab_small, alignment=2,
         ))],
        [_p(model["laboratory_address"], lab_small), ""],
    ], colWidths=[3.75*inch, 2.7*inch])
    header.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("SPAN", (0, 2), (1, 2)),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("LINEBELOW", (0, 2), (-1, 2), 1.1, colors.black),
    ]))
    authorization = Table([
        [_p("Examiner approval — Morgan Voss", lab_label),
         signature_mark(1),
         _p("11 February 2026", lab_small)],
        [_p("Technical review — Leena Park", lab_label),
         signature_mark(2),
         _p("11 February 2026", lab_small)],
    ], colWidths=[2.0*inch, 3.0*inch, 1.45*inch])
    authorization.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 2),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 2.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
        ("LINEBELOW", (0, 0), (-1, -1), 0.35, colors.HexColor("#999999")),
    ]))
    story = [header, Spacer(1, 7), _p("LIMITED EXAMINATION REPORT", lab_h1),
              lab_table([["Laboratory no.", model["record_id"], "Submitting case", model["case_reference"]],
                         ["Examiner", model["examiner"], "Report date", model["represented_date"]],
                         ["Technical reviewer", model["technical_reviewer"], "Status", "Final · issue 1"],
                         ["Submitted by", "Ada Bell / HPHC", "Distribution", "Submitting case only"]],
                        [0.95*inch, 2.0*inch, 1.0*inch, 2.5*inch], header=False),
              _p("Items received and custody", lab_h2),
              lab_table([["Date / time", "Released by", "Received / location", "Control"], *model["custody_events"]],
                        [1.1*inch, 1.35*inch, 1.45*inch, 2.55*inch]),
              lab_table([["Item", "Description", "Packaging / condition"], *model["items"]],
                        [0.65*inch, 3.55*inch, 2.25*inch]),
              _p("Examination-derived samples", lab_h2),
              lab_table([["Sample", "Origin / preparation", "Storage / disposition"], *model["derived_samples"]],
                        [0.7*inch, 3.5*inch, 2.25*inch]),
              _p("Requested examination", lab_h2),
              _p("Characterize the questioned line material, surface relationship, and loose fiber; document the attached clipping paper. Assess whether the examinations support common manufacture or common age. Authorship, printer-source comparison, and destructive paper dating were outside scope.", lab_body),
              _p("Methods", lab_h2),
              lab_table([
                  ["Code", "Procedure", "Instrument / control", "Output / effect"],
                  *[[code, procedure, instrument, f"{output}; {effect}"]
                    for code, procedure, instrument, output, effect in model["methods"]],
              ], [0.5*inch, 2.25*inch, 1.55*inch, 2.15*inch]),
              PageBreak(),
              _p("Result record", lab_h2),
              lab_table([["Output", "Recorded result", "Interpretive limit"], *model["results"]],
                        [1.4*inch, 2.85*inch, 2.2*inch]),
              _p("Observations", lab_h2)]
    story.extend(_p(f"{index}. {value}", lab_body) for index, value in enumerate(model["observations"], 1))
    story += [_p("Evaluation", lab_h2), _p(model["conclusion"], lab_body),
              _p("Reporting limitations", lab_h2), _p(model["limitations"], lab_body),
              _p("Output disposition", lab_h2),
              lab_table([["Output", "Repository", "Disposition"], *model["output_disposition"]],
                        [2.05*inch, 2.95*inch, 1.45*inch]),
              _p("Report authorization", lab_h2),
              authorization]
    return _document(
        model, metadata, story, margins=(0.7, 0.65, 0.55, 0.8),
        footer_factory=_lab_footer_callback,
    )


def _render_access(model: dict[str, Any], metadata: dict[str, Any]) -> bytes:
    _ensure_office_fonts()
    access_body = ParagraphStyle(
        "AccessBody", parent=BODY, fontName="VeraOffice", fontSize=8.2,
        leading=10, textColor=colors.black, spaceAfter=3,
    )
    access_small = ParagraphStyle(
        "AccessSmall", parent=access_body, fontSize=7.2, leading=8.4,
    )
    access_label = ParagraphStyle(
        "AccessLabel", parent=access_small, fontName="VeraOffice-Bold",
    )
    access_title = ParagraphStyle(
        "AccessTitle", parent=access_body, fontName="VeraOffice-Bold",
        fontSize=14, leading=17, spaceAfter=6,
    )

    def access_table(rows: list[list[Any]], widths: list[float], *, header=True) -> Table:
        cells = [[
            _p(value, access_label if header and row_index == 0 else access_small)
            for value in row
        ] for row_index, row in enumerate(rows)]
        table = Table(cells, colWidths=widths, repeatRows=1 if header else 0)
        style = [
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 3),
            ("RIGHTPADDING", (0, 0), (-1, -1), 3),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#b0b0b0")),
        ]
        if header:
            style.extend([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dddddd")),
                ("LINEABOVE", (0, 0), (-1, 0), 0.6, colors.HexColor("#555555")),
                ("LINEBELOW", (0, 0), (-1, 0), 0.6, colors.HexColor("#555555")),
            ])
        table.setStyle(TableStyle(style))
        return table

    story = [
        _p(model["system"], ParagraphStyle(
            "AccessSystem", parent=access_body, fontName="VeraOffice-Bold",
            fontSize=10, leading=12,
        )),
        _p(model["organization"], access_small),
        Spacer(1, 5),
        _p(model["report_name"], access_title),
        access_table([
            ["Report ID", model["record_id"], "Generated", "2026-02-11 21:14:00 EST"],
            ["Site", model["site"], "Controller", model["controller"]],
            ["Database", model["database"], "Operator / workstation", f"{model['operator']} / {model['workstation']}"],
            ["Period", model["period"], "Sort", "Controller event sequence (ascending)"],
            ["Criteria", model["filter"], "", ""],
        ], [0.85*inch, 4.0*inch, 1.25*inch, 3.9*inch], header=False),
        Spacer(1, 6),
        access_table([
            ["Sequence", "Time", "Credential", "Cardholder", "Door / device", "Event message", "Class"],
            *model["events"],
        ], [0.75*inch, 0.75*inch, 1.0*inch, 1.4*inch, 1.9*inch, 3.4*inch, 0.8*inch]),
        Spacer(1, 5),
        _p(model["integrity_note"], access_small),
        access_table([
            ["Query", f"QRY-{model['export_job']}", "Rows", str(len(model["events"])),
             "Time zone", "America/New_York", "Output", "PDF"],
        ], [0.55*inch, 1.15*inch, 0.45*inch, 0.5*inch, 0.7*inch, 2.1*inch, 0.55*inch, 0.75*inch], header=False),
    ]
    return _document(model, metadata, story, pagesize=landscape(letter),
                     margins=(0.5, 0.5, 0.42, 0.58),
                     footer_factory=_memo_footer_callback)


def _money(value: Any) -> str:
    return f"${float(value):,.2f}"


def _render_tenant(model: dict[str, Any], metadata: dict[str, Any]) -> bytes:
    _ensure_office_fonts()
    address = (f"{model['street']}, Apt {model['unit']}, {model['municipality']}, "
               f"{model['state']} {model['zip']}")
    tenant_body = ParagraphStyle(
        "TenantBody", parent=BODY, fontName="VeraOffice", fontSize=8.5,
        leading=10.4, textColor=colors.black, spaceAfter=3,
    )
    tenant_small = ParagraphStyle(
        "TenantSmall", parent=tenant_body, fontSize=8.4, leading=10.2,
    )
    tenant_label = ParagraphStyle(
        "TenantLabel", parent=tenant_small, fontName="VeraOffice-Bold",
    )
    tenant_title = ParagraphStyle(
        "TenantTitle", parent=tenant_body, fontName="VeraOffice-Bold",
        fontSize=14, leading=17, spaceAfter=6,
    )

    def ledger_table(rows: list[list[Any]], widths: list[float], *, header=True) -> Table:
        cells = [[
            _p(value, tenant_label if header and row_index == 0 else tenant_small)
            for value in row
        ] for row_index, row in enumerate(rows)]
        table = Table(cells, colWidths=widths, repeatRows=1 if header else 0)
        commands = [
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 3),
            ("RIGHTPADDING", (0, 0), (-1, -1), 3),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.HexColor("#aaaaaa")),
        ]
        if header:
            commands.extend([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e4e4e4")),
                ("LINEABOVE", (0, 0), (-1, 0), 0.6, colors.HexColor("#555555")),
                ("LINEBELOW", (0, 0), (-1, 0), 0.6, colors.HexColor("#555555")),
            ])
        table.setStyle(TableStyle(commands))
        return table

    story = [
        _p(model["organization"], ParagraphStyle(
            "TenantSystem", parent=tenant_body, fontName="VeraOffice-Bold",
            fontSize=10.5, leading=12,
        )),
        _p("Resident Accounts", tenant_small),
        Spacer(1, 5),
        _p("Resident Ledger", tenant_title),
        ledger_table([
            ["Property", f"{model['property']} / {model['property_code']}",
             "Unit / account", f"{model['unit']} / {model['account_number']}"],
            ["Premises", address, "Resident", model["tenant"]],
            ["Lease term", f"{model['term_start']} through {model['term_end']}",
             "Resident status", model["occupancy_status"]],
            ["Report ID", model["record_id"], "Generated", "2026-02-11 21:22:00 EST"],
            ["Report period", model["report_period"], "Portfolio", model["portfolio"]],
            ["Monthly rent", _money(model["monthly_rent"]), "Deposit held", _money(model["deposit"])],
        ], [0.85*inch, 2.35*inch, 1.05*inch, 2.2*inch], header=False),
        Spacer(1, 8),
        _p("Account activity", ParagraphStyle(
            "TenantSection", parent=tenant_body, fontName="VeraOffice-Bold",
            fontSize=9.2, leading=11, spaceBefore=3, spaceAfter=3,
        )),
        ledger_table([
            ["Post date", "Type", "Reference", "Description", "Charges", "Receipts", "Rent balance", "Deposit held"],
            *model["transactions"],
        ], [0.85*inch, 0.45*inch, 0.95*inch, 1.05*inch, 0.68*inch, 0.72*inch, 0.75*inch, 0.75*inch]),
        Spacer(1, 6),
        ledger_table([
            ["Aging date", "Current", "1–30 days", "31–60 days", "61–90 days", "Over 90", "Credits"],
            [model["represented_date"], "$0.00", "$0.00", "$0.00", "$0.00", "$0.00", "$0.00"],
        ], [1.05*inch, 0.88*inch, 0.88*inch, 0.88*inch, 0.88*inch, 0.88*inch, 0.88*inch]),
    ]
    return _document(
        model, metadata, story, pagesize=letter,
        margins=(0.65, 0.65, 0.55, 0.65), footer_factory=_tenant_footer_callback,
    )


def _render_voicemail(model: dict[str, Any], metadata: dict[str, Any]) -> bytes:
    _ensure_office_fonts()
    mobile_body = ParagraphStyle(
        "MobileBody", parent=BODY, fontName="VeraOffice", fontSize=8.7,
        leading=10.8, textColor=colors.black, spaceAfter=4,
    )
    mobile_small = ParagraphStyle(
        "MobileSmall", parent=mobile_body, fontSize=7.8, leading=9.5,
    )
    mobile_label = ParagraphStyle(
        "MobileLabel", parent=mobile_small, fontName="VeraOffice-Bold",
    )
    mobile_heading = ParagraphStyle(
        "MobileHeading", parent=mobile_body, fontName="VeraOffice-Bold",
        fontSize=9, leading=11, spaceBefore=7, spaceAfter=3,
    )
    mobile_title = ParagraphStyle(
        "MobileTitle", parent=mobile_body, fontName="VeraOffice-Bold",
        fontSize=13, leading=16, spaceAfter=6,
    )
    mobile_mono = ParagraphStyle(
        "MobileMono", parent=mobile_small, fontName="Courier", fontSize=7.2,
        leading=9,
    )

    def mobile_table(rows: list[list[Any]], widths: list[float], *, header=True) -> Table:
        cells = [[
            _p(value, mobile_label if header and row_index == 0 else mobile_small)
            for value in row
        ] for row_index, row in enumerate(rows)]
        table = Table(cells, colWidths=widths, repeatRows=1 if header else 0)
        commands = [
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 3),
            ("RIGHTPADDING", (0, 0), (-1, -1), 3),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.HexColor("#a8a8a8")),
        ]
        if header:
            commands.extend([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e5e5e5")),
                ("LINEABOVE", (0, 0), (-1, 0), 0.6, colors.HexColor("#555555")),
                ("LINEBELOW", (0, 0), (-1, 0), 0.6, colors.HexColor("#555555")),
            ])
        table.setStyle(TableStyle(commands))
        return table

    org = ParagraphStyle(
        "MobileOrg", parent=mobile_body, fontName="VeraOffice-Bold",
        fontSize=10.5, leading=12,
    )
    story = [
        _p(model["organization"], org),
        _p(f"{model['department']} · {model['form_number']} · {model['form_revision']}", mobile_small),
        Spacer(1, 4),
        _p("DV-04 — Limited Mobile File Collection", mobile_title),
        mobile_table([
            ["Case / record", f"IR-26-07 / {model['record_id']}", "Status", "REVIEWED"],
            ["Operator", model["prepared_by"], "Prepared", model["prepared_at"]],
            ["Reviewer", model["reviewed_by"], "Reviewed", model["reviewed_at"]],
        ], [0.95*inch, 2.8*inch, 0.75*inch, 1.95*inch], header=False),
        _p("Document control", mobile_heading),
        mobile_table([
            ["Issuing unit", model["issuing_unit"]],
            ["Record series", model["record_series"]],
            ["Retention", model["retention_rule"]],
            ["Case record", model["case_system"]],
        ], [1.05*inch, 5.4*inch], header=False),
        _p("1. Authority and collection boundary", mobile_heading),
        mobile_table([
            ["Authority", model["collection_authority"]],
            ["Authorized scope", model["collection_scope"]],
        ], [1.05*inch, 5.4*inch], header=False),
        _p("2. Device and message observed", mobile_heading),
        mobile_table([
            ["Evidence item", "Make / model", "OS / build"],
            ["IR-26-07-D02", model["device_model"], model["device_os"]],
            ["Device identifier", model["device_identifier"], model["device_state"]],
            ["Account label", model["account"], "Application: " + model["source_application"]],
            ["Message", model["message_id"], f"Received {model['received_at']} · {model['duration']}"],
            ["Displayed parties", model["from_name"], "To " + model["to_name"]],
        ], [1.1*inch, 2.5*inch, 2.85*inch]),
        _p("3. Collection method and environment", mobile_heading),
        mobile_table([
            ["Method", model["collection_method"]],
            ["Workstation", model["workstation"]],
            ["Hash utility", model["hash_tool"]],
        ], [1.05*inch, 5.4*inch], header=False),
        _p("4. Operator event log · 11 Feb 2026 EST", mobile_heading),
        mobile_table([
            ["Time", "Device / volume", "Operator observation or action"],
            *model["acquisition_events"],
        ], [0.75*inch, 1.45*inch, 4.25*inch]),
        PageBreak(),
        _p(model["organization"], org),
        _p(f"{model['department']} · {model['form_number']} · {model['form_revision']} · IR-26-07 / {model['record_id']}", mobile_small),
        Spacer(1, 4),
        _p("DV-04 continued — File Verification / Listening Notes", mobile_title),
        _p("5. Collected file", mobile_heading),
        mobile_table([
            ["Export filename", model["source_filename"], "Bytes", model["audio_bytes"]],
            ["Staging path", model["staging_path"], "", ""],
            ["Evidence path", model["evidence_path"], "", ""],
            ["Repository locator", model["repository_locator"], "State", "READ ONLY"],
        ], [1.0*inch, 4.0*inch, 0.55*inch, 0.9*inch], header=False),
        _p("6. Integrity calculations", mobile_heading),
        mobile_table([
            ["Calculation", "Recorded value"],
            ["Staging", model["hash_first"]],
            ["Evidence", model["hash_second"]],
        ], [0.8*inch, 5.65*inch]),
        _p(model["audio_hash"], mobile_mono),
        _p(model["preservation"], mobile_small),
        _p("7. Listening record", mobile_heading),
        _p(model["transcription_method"], mobile_small),
        mobile_table([
            ["Offset", "Transcript / audible event", "Annotation"],
            *model["segments"],
        ], [0.7*inch, 4.1*inch, 1.65*inch]),
        _p("8. Scope and interpretation limits", mobile_heading),
        _p(model["limitations"], mobile_small),
        _p("9. Review disposition", mobile_heading),
        mobile_table([
            ["Prepared", f"{model['prepared_by']} · {model['prepared_at']}"],
            ["Reviewed", f"{model['reviewed_by']} · {model['review_entry']}"],
            ["Export", f"CaseTrack job {model['case_export_job']} · {model['exported_at']}"],
            ["Disposition", "M4A export retained at evidence path; this PDF is the collection and listening worksheet"],
        ], [0.85*inch, 5.6*inch], header=False),
    ]
    return _document(
        model, metadata, story, margins=(0.65, 0.65, 0.82, 0.7),
        footer_factory=_mobile_footer_callback,
    )


def _wrap_lines(c: canvas.Canvas, text: str, font: str, size: float,
                width: float) -> list[str]:
    words = text.split()
    result: list[str] = []
    line = ""
    for word in words:
        trial = f"{line} {word}".strip()
        if c.stringWidth(trial, font, size) <= width:
            line = trial
        else:
            if line:
                result.append(line)
            line = word
    if line:
        result.append(line)
    return result


def _render_card(model: dict[str, Any], metadata: dict[str, Any]) -> bytes:
    width, height = landscape(letter)
    target = io.BytesIO()
    c = canvas.Canvas(target, pagesize=(width, height), invariant=1)
    c.setCreator(metadata["creator"]); c.setProducer(metadata["producer"])
    c.setTitle(_document_title(model)); c.setAuthor(_document_author(model))
    c.setSubject(_document_subject(model))

    def wrapped(text: str, x: float, y: float, max_width: float, *,
                font="Helvetica", size=9.0, leading=11.0,
                color=colors.black) -> float:
        c.setFillColor(color); c.setFont(font, size)
        for line in _wrap_lines(c, text, font, size, max_width):
            c.drawString(x, y, line)
            y -= leading
        return y

    # A printable safety sign: ordinary, high-legibility, and narrowly scoped.
    margin = 0.28 * inch
    c.setFillColor(colors.white); c.rect(0, 0, width, height, fill=1, stroke=0)
    c.setStrokeColor(colors.black); c.setLineWidth(0.8)
    c.rect(margin, margin, width-2*margin, height-2*margin, fill=0, stroke=1)
    c.setFillColor(colors.HexColor("#b5121b"))
    c.rect(margin+4, height-margin-0.62*inch, width-2*margin-8, 0.58*inch, fill=1, stroke=0)
    c.setFillColor(colors.white); c.setFont("Helvetica-Bold", 25)
    c.drawString(margin+0.18*inch, height-margin-0.43*inch, "DANGER")
    c.setFont("Helvetica-Bold", 15)
    c.drawRightString(width-margin-0.18*inch, height-margin-0.39*inch,
                      "PERMIT-REQUIRED CONFINED SPACE")
    c.setFillColor(colors.black); c.setFont("Helvetica-Bold", 15)
    c.drawString(margin+0.18*inch, height-margin-0.84*inch,
                 "NON-ENTRY EMERGENCY RELEASE — R-2 / P-2")
    c.setFont("Helvetica", 8.5)
    c.drawRightString(width-margin-0.18*inch, height-margin-0.82*inch,
                      f"{model['record_id']} · {model['revision']}")
    c.setFont("Helvetica", 9)
    c.drawString(margin+0.18*inch, height-margin-1.04*inch,
                 f"POST AT {model['location'].upper()} · ER-2 RED RING / DR-2 DOOR / ES-2 STOP")

    left_x = margin + 0.18*inch
    left_w = 5.85*inch
    right_x = left_x + left_w + 0.20*inch
    right_w = width-margin-right_x-0.18*inch
    y = height-margin-1.34*inch
    c.setFillColor(colors.HexColor("#8a1017")); c.setFont("Helvetica-Bold", 11)
    y = wrapped(model["scenario"], left_x, y, left_w,
                font="Helvetica-Bold", size=10.5, leading=12,
                color=colors.HexColor("#8a1017"))
    c.setFillColor(colors.black); c.setFont("Helvetica-Bold", 12)
    c.drawString(left_x, y-0.06*inch, "IMMEDIATE ACTION — STAY IN THE CORRIDOR")
    y -= 0.48*inch
    for index, step in enumerate(model["steps"], 1):
        c.setFillColor(colors.black); c.rect(left_x, y-0.04*inch, 0.30*inch, 0.30*inch, fill=1, stroke=0)
        c.setFillColor(colors.white); c.setFont("Helvetica-Bold", 11)
        c.drawCentredString(left_x+0.15*inch, y+0.055*inch, str(index))
        y = wrapped(step, left_x+0.40*inch, y+0.15*inch, left_w-0.42*inch,
                    font="Helvetica-Bold" if index == 2 else "Helvetica",
                    size=10.2, leading=12.8)
        y -= 0.18*inch

    c.setFillColor(colors.HexColor("#fff1bf")); c.setStrokeColor(colors.HexColor("#6f5400")); c.setLineWidth(1)
    c.rect(left_x, y-0.74*inch, left_w, 0.72*inch, fill=1, stroke=1)
    c.setFillColor(colors.HexColor("#4f3b00")); c.setFont("Helvetica-Bold", 10)
    c.drawString(left_x+0.10*inch, y-0.20*inch, "IF ER-2 DOES NOT OPEN DR-2")
    wrapped(model["release_failure"], left_x+0.10*inch, y-0.39*inch,
            left_w-0.20*inch, size=8.8, leading=10.3,
            color=colors.HexColor("#3d2b00"))
    y -= 0.88*inch
    c.setFillColor(colors.HexColor("#eeeeee")); c.setStrokeColor(colors.black)
    c.rect(left_x, y-0.66*inch, left_w, 0.64*inch, fill=1, stroke=1)
    c.setFillColor(colors.black); c.setFont("Helvetica-Bold", 10)
    c.drawString(left_x+0.10*inch, y-0.20*inch, "NEVER ENTER R-2 FOR RESCUE · NEVER REACH PAST THE P-2 GUARD")
    wrapped("ES-2 is not lockout. After ER-2 operation, keep P-2 stopped until the Facilities Operations Supervisor releases it.",
            left_x+0.10*inch, y-0.41*inch, left_w-0.20*inch,
            font="Helvetica-Bold", size=8.8, leading=10.3)

    # Monochrome equipment orientation sketch, not an explanatory infographic.
    diagram_top = height-margin-1.30*inch
    diagram_bottom = diagram_top-3.05*inch
    c.setStrokeColor(colors.black); c.setLineWidth(1.2)
    c.rect(right_x, diagram_bottom, right_w, diagram_top-diagram_bottom, fill=0, stroke=1)
    c.setFillColor(colors.black); c.setFont("Helvetica-Bold", 10)
    c.drawString(right_x+0.10*inch, diagram_top-0.20*inch, "CORRIDOR-SIDE ORIENTATION")
    c.setFont("Helvetica-Bold", 8.3)
    c.drawString(right_x+0.10*inch, diagram_top-0.40*inch, "DO NOT CROSS THE DR-2 THRESHOLD")
    c.setFont("Helvetica", 7)
    c.drawRightString(right_x+right_w-0.10*inch, diagram_top-0.20*inch, "NOT TO SCALE")
    pump_x, pump_y = right_x+0.35*inch, diagram_bottom+0.86*inch
    c.setFillColor(colors.white); c.rect(pump_x, pump_y, 1.75*inch, 0.80*inch, fill=1, stroke=1)
    c.setFillColor(colors.black); c.setFont("Helvetica-Bold", 10.5)
    c.drawCentredString(pump_x+0.875*inch, pump_y+0.49*inch, "P-2 / ASSET 0227")
    c.setFont("Helvetica", 7.5)
    c.drawCentredString(pump_x+0.875*inch, pump_y+0.26*inch, "PUMP GUARD")
    c.drawCentredString(pump_x+0.875*inch, pump_y+0.09*inch, "ES-2 STOP ON CORRIDOR FACE")
    door_x = right_x+right_w-0.70*inch
    c.line(door_x, diagram_bottom+0.52*inch, door_x, diagram_top-0.58*inch)
    c.setFont("Helvetica-Bold", 9); c.drawString(door_x+0.08*inch, diagram_top-0.82*inch, "R-2")
    c.setFont("Helvetica", 7.5); c.drawString(door_x+0.08*inch, diagram_top-1.02*inch, "NO ENTRY")
    ring_x, ring_y = pump_x+1.92*inch, pump_y+0.28*inch
    c.setFillColor(colors.HexColor("#b5121b")); c.circle(ring_x, ring_y, 8, fill=1, stroke=0)
    c.setFont("Helvetica-Bold", 8.5); c.drawString(ring_x+0.16*inch, ring_y+2, "ER-2 RED COVER")
    c.setFont("Helvetica", 7.2); c.drawString(ring_x+0.16*inch, ring_y-8, "RING · 44 in AFF")
    c.setStrokeColor(colors.HexColor("#b5121b")); c.setLineWidth(2)
    c.line(ring_x, ring_y-0.18*inch, door_x, ring_y-0.18*inch)
    c.setFillColor(colors.black); c.setFont("Helvetica-Bold", 8)
    c.drawString(door_x-0.42*inch, ring_y-0.34*inch, "DR-2")
    c.setFont("Helvetica", 8)
    c.drawString(right_x+0.18*inch, diagram_bottom+0.34*inch, "← WEST / STAIRS TO GALLERY")
    c.drawRightString(right_x+right_w-0.18*inch, diagram_bottom+0.34*inch, "EAST STONE WALL →")
    c.setFont("Helvetica-Bold", 7.5)
    c.drawCentredString(right_x+right_w/2, diagram_bottom+0.17*inch, "SERVICE CORRIDOR")
    c.setFont("Helvetica-Bold", 7.5)
    c.drawString(right_x+0.18*inch, diagram_bottom+0.03*inch, "▲ YOU ARE HERE — EIC-04 POSTED BESIDE ER-2")

    box_y = diagram_bottom-0.20*inch
    c.setFillColor(colors.black); c.setFont("Helvetica-Bold", 11)
    c.drawString(right_x, box_y, "WORK BOUNDARY")
    box_y = wrapped(model["loto_boundary"], right_x, box_y-0.20*inch,
                    right_w, size=9.0, leading=11.0)
    c.setStrokeColor(colors.black); c.line(right_x, box_y-0.05*inch, width-margin-0.18*inch, box_y-0.05*inch)
    box_y -= 0.27*inch
    c.setFont("Helvetica-Bold", 11); c.drawString(right_x, box_y, "AFTER ER-2 OPERATION")
    box_y = wrapped(model["restoration"], right_x, box_y-0.20*inch,
                    right_w, size=9.0, leading=11.0)
    box_y = wrapped("Notify Site Emergency Control and Facilities. Open an incident report and a P-2 work order; record inspection, repair, and restoration approval.",
                    right_x, box_y-0.05*inch, right_w, size=9.0, leading=11.0)

    # A field-posting footer, not a facsimile of the DMS approval screen.  The
    # retrieval path and inspection blank are the useful controls at point of use.
    footer_y = margin+0.40*inch
    c.setStrokeColor(colors.black); c.setLineWidth(0.7)
    c.line(margin+0.12*inch, footer_y+0.45*inch, width-margin-0.12*inch, footer_y+0.45*inch)
    c.setFillColor(colors.black); c.setFont("Helvetica", 7.2)
    c.drawString(margin+0.18*inch, footer_y+0.25*inch,
                 f"{model['record_id']} · {model['revision']} · issued {model['issued_date']}")
    c.drawRightString(width-margin-0.18*inch, footer_y+0.25*inch,
                      model["approved_by"])
    c.drawString(margin+0.18*inch, footer_y+0.07*inch,
                 "Current revision: Facilities DMS > Safety Documents > EIC-04")
    c.drawRightString(width-margin-0.18*inch, footer_y+0.07*inch,
                      "Post: east wall adjacent to ER-2")
    c.drawString(margin+0.18*inch, footer_y-0.11*inch,
                 "Printed copies are uncontrolled; Facilities verifies the posted revision during PM-P2-06.")
    c.drawRightString(width-margin-0.18*inch, footer_y-0.11*inch,
                      "MONTHLY FIELD CHECK   date __________   initials ______")
    c.drawString(margin+0.18*inch, footer_y-0.29*inch,
                 "Governing procedures: EAP-01 · CSP-03 · ECP-LOTO-02 · PM-P2-06")
    c.showPage(); c.save()
    return _finalize(target.getvalue(), metadata)


RENDERERS = {
    "museum_research_note": _render_research,
    "curatorial_chronology": _render_chronology,
    "conservation_examination": _render_conservation,
    "access_event_report": _render_access,
    "tenant_account_ledger": _render_tenant,
    "voicemail_evidence_report": _render_voicemail,
    "pump_emergency_card": _render_card,
}


def render_artifact(
    model: dict[str, Any], *, metadata: dict[str, Any],
    defect: dict | None = None,
) -> bytes:
    shown = _display_model(model, defect)
    return RENDERERS[shown["kind"]](shown, metadata)


def _reading_copy(model: dict[str, Any]) -> list[str]:
    """Literal, non-interpretive strings exposed by the artifact."""
    kind = model["kind"]
    common = [model["organization"], model["record_id"], model["represented_date"]]
    if kind == "museum_research_note":
        return common + [model["records_series"], model["project"],
                         model["loan_number"], model["object_id"],
                         model["receipt_id"], model["lender"],
                         model["record_status"], model["current_location"],
                         model["handling_class"], model["rights_status"],
                         model["object_description"],
                         model["object_custody"], model["subject"],
                         model["question"], model["finding"],
                         *(cell for row in model["sources"] for cell in row),
                         *model["source_locators"],
                         *(cell for row in model["research_log"] for cell in row),
                         model["review_authority"], model["reviewed_at"],
                         model["retention"],
                         model["limitations"]]
    if kind == "curatorial_chronology":
        return common + [model["title"], model["scope"],
                         *(cell for row in model["rows"] for cell in row),
                         *(cell for row in model["source_notes"] for cell in row),
                         model["conclusion"]]
    if kind == "conservation_examination":
        return common + [model["case_reference"], model["examiner"],
                         *(cell for row in model["custody_events"] for cell in row),
                         *(cell for row in model["items"] for cell in row),
                         *(cell for row in model["derived_samples"] for cell in row),
                         *(cell for row in model["methods"] for cell in row),
                         *(cell for row in model["results"] for cell in row),
                         *(cell for row in model["output_disposition"] for cell in row),
                         *model["observations"], model["conclusion"], model["limitations"]]
    if kind == "access_event_report":
        return common + [model["report_name"], model["filter"],
                         *(cell for row in model["events"] for cell in row), model["integrity_note"]]
    if kind == "tenant_account_ledger":
        return common + [model["property"], model["tenant"], model["account_number"],
                         model["term_start"], model["term_end"], str(model["monthly_rent"]),
                         str(model["deposit"]), model["deposit_reference"],
                         model["deposit_received"],
                         *(cell for row in model["transactions"] for cell in row)]
    if kind == "voicemail_evidence_report":
        return common + [model["device"], model["account"],
                         model["form_number"], model["form_revision"],
                         model["issuing_unit"], model["record_series"],
                         model["retention_rule"], model["case_system"],
                         model["case_export_job"], model["review_entry"],
                         model["device_model"], model["device_identifier"],
                         model["device_os"], model["device_state"],
                         model["from_name"], model["to_name"],
                         model["received_at"], model["duration"],
                         model["message_id"], model["source_application"],
                         model["source_filename"], model["audio_bytes"],
                         model["audio_hash"], model["repository_locator"],
                         model["collection_scope"], model["collection_authority"],
                         model["collection_method"], model["workstation"],
                         model["staging_path"], model["evidence_path"],
                         model["hash_tool"], model["hash_first"],
                         model["hash_second"], model["preservation"],
                         *(cell for row in model["acquisition_events"] for cell in row),
                         *(cell for row in model["segments"] for cell in row),
                         model["prepared_by"], model["reviewed_by"],
                         model["prepared_at"], model["reviewed_at"],
                         model["transcription_method"], model["limitations"]]
    return common + [model["issued_date"], model["location"], model["revision"],
                     model["owner"], model["approved_by"], model["supersedes"],
                     model["approval_record"], model["classification"],
                     model["source_record"], model["print_control"],
                     model["scenario"], *model["steps"],
                     model["release_failure"], model["loto_boundary"],
                     model["restoration"], model["procedures"]]


sample_research_note = partial(sample_artifact, kind="museum_research_note")
sample_chronology = partial(sample_artifact, kind="curatorial_chronology")
sample_conservation = partial(sample_artifact, kind="conservation_examination")
sample_access = partial(sample_artifact, kind="access_event_report")
sample_tenant_account = partial(sample_artifact, kind="tenant_account_ledger")
sample_voicemail = partial(sample_artifact, kind="voicemail_evidence_report")
sample_pump_card = partial(sample_artifact, kind="pump_emergency_card")
