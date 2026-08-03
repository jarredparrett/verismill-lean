"""vintage: typewritten-era legal documents, delivered as period-honest scans.

A 1987 agreement cannot be a vector PDF: the PDF format shipped in 1993, so
an authentic artifact is a SCAN of a typewritten original — image pages with
scanner metadata dated at digitization time, plus the invisible OCR text
layer a Paper-Capture workflow adds. Claiming a 1987 CreationDate would be
the forensic tell, not avoiding one.

Two stages:
1. a Courier pleading-paper renderer (California 28-line numbered paper,
   double vertical rule, typed caption, wet-ink signatures, notary block);
2. a seeded scan pipeline — rasterize, small rotation, speckle, contrast
   jitter, grayscale JPEG — re-embedded page-per-page with an invisible
   (render mode 3) text layer so the file is searchable like a real
   Paper-Capture output, and testable via the same text-extraction lens.

Period discipline for the composer lives in the model, not here: an
agreement dated 1987 cites the California Civil Code (the Family Code
did not exist until 1994) and cannot cite the Hague Abduction Convention
(US accession 1988). Capability tests pin those.

Defect hooks touch exactly one fact each: a twin's date of birth that
diverges, a marriage date that postdates the births.
"""

from __future__ import annotations

import io
import random
import re

from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas as rl_canvas

from . import assets, scan

PAGE_W, PAGE_H = letter
LINE_1_Y = 740          # baseline of numbered line 1
LEADING = 23.0          # double-spaced typewriter
N_LINES = 28
NUM_X = 62              # line-number column
RULE_X1, RULE_X2 = 76, 79
TEXT_X = 90
TEXT_RIGHT = 576
CHARS = 66              # Courier 11 wrap width across 6.75"
FONT = ("Courier", 11)


# ---------------------------------------------------------------------------
# Canon — caller-supplied world facts, never sampled. Texture (addresses,
# counsel, exact dates inside canon-consistent windows) is seeded in
# sample_msa.
#
# The canon is DATA, not code. Pass your own to sample_msa(rng, canon=...);
# the default below is an invented family, shipped so the emitter runs out of
# the box. Every key here is load-bearing — the composer reads all of them,
# and a canon missing one will fail loudly rather than render a blank.
# ---------------------------------------------------------------------------

DEFAULT_CANON = {
    "husband": "ANDREW COLE HAVERFORD",
    "wife": "MARGUERITE ROSE DELACROIX HAVERFORD",
    "wife_maiden": "DELACROIX",
    "twin_a": "CLARE HAVERFORD",        # remains with father
    "twin_b": "JUNE HAVERFORD",         # to mother; takes the maiden name
    "twin_b_new": "JUNE DELACROIX",
    "dob": "August 4, 1986",
    "married_aboard": "the chapel of Sainte-Anne, Quebec City, during a "
                      "December sitting of the parties' families",
    "ranch": "the Haverford orchard and packing house, Tulare County, "
             "California",
    "wife_trade": "restorer of antiquarian bindings",
    "wife_city": "Montreal, Quebec",
    # Locale — every place the instrument names follows from these, so a
    # replacement canon relocates the document coherently. The forum stays
    # in California by construction: the pleading paper is California's
    # 28-line numbered stock and the composer cites the California Civil
    # Code, so a canon that moves the forum out of state would render an
    # instrument that contradicts its own paper.
    "forum_city": "Visalia, California",
    "husband_county": "Tulare County, California",
    "husband_street": "Avenue 384",
    "husband_counsel_addr": ["214 West Main Street, Suite 300",
                             "Visalia, California 93291"],
    "husband_counsel_area": "209",            # Central Valley, pre-1997 split
    "wife_counsel_addr": ["601 California Street, 14th Floor",
                          "San Francisco, California 94108"],
    "wife_counsel_area": "415",
    "wife_street": "Rue Sherbrooke Ouest",
    "wife_locality": "Montreal, Quebec H3A 1G1, Canada",
    "court_county": "TULARE",                 # caption + notary venue
    "residence_short": "Visalia",
    "wife_forum": "the Province of Quebec",   # the foreign forum a
                                              # sister-state order runs to
}

_CANON_KEYS = frozenset(DEFAULT_CANON)


def sample_msa(rng: random.Random, *, canon: dict | None = None) -> dict:
    """Seeded texture around a fixed canon: case number, counsel, notary,
    addresses, and exact dates drawn inside canon-consistent windows
    (married late 1985; twins born the following year; separated while the
    twins were infants; executed early 1987). `canon` supplies the world's
    fixed facts — see DEFAULT_CANON for the required keys."""
    canon = dict(DEFAULT_CANON if canon is None else canon)
    missing = _CANON_KEYS - set(canon)
    if missing:
        raise ValueError(f"canon missing required keys: {sorted(missing)}")
    marriage_day = rng.randint(2, 26)
    sep_day = rng.randint(2, 27)
    exec_day = rng.randint(3, 27)
    exec_month = rng.choice(["February", "March", "March", "April"])
    return {
        **canon,
        "case_no": f"D-{rng.randint(8700, 8799)}-{rng.randint(100, 899)}",
        "marriage_date": f"November {marriage_day}, 1985",
        "separation_date": f"December {sep_day}, 1986",
        "execution_date": f"{exec_month} {exec_day}, 1987",
        "husband_counsel": {
            "name": rng.choice(["JACOB R. WHEELER", "DONALD F. McNAB"]),
            "bar": str(rng.randint(61000, 96000)),
            "firm": "WHEELER & McNAB",
            "addr": list(canon["husband_counsel_addr"]),
            "phone": f"({canon['husband_counsel_area']}) 224-"
                     f"{rng.randint(2000, 8999)}"},
        "wife_counsel": {
            "name": rng.choice(["MARGARET H. COLE", "PATRICIA A. LUNDGREN"]),
            "bar": str(rng.randint(71000, 118000)),
            "firm": "COLE, LUNDGREN & PRICE",
            "addr": list(canon["wife_counsel_addr"]),
            "phone": f"({canon['wife_counsel_area']}) 391-"
                     f"{rng.randint(2000, 8999)}"},
        "husband_addr": f"{rng.randint(1000, 4800)} {canon['husband_street']}, "
                        f"{canon['husband_county']}",
        "wife_addr": f"{rng.randint(8, 40)} {canon['wife_street']}, "
                     f"{canon['wife_locality']}",
        "notary": {"name": rng.choice(["DOROTHY M. ALVES", "CAROL J. STEINER"]),
                   "expires": f"{rng.choice(['June', 'September'])} "
                              f"{rng.randint(2, 28)}, 19{rng.randint(88, 90)}"},
        # the lawyered record around the extraordinary arrangement
        "psychiatrist": "Charles W. Ellison, M.D.",
        "minors_counsel": {"name": "RICHARD A. BELL",
                           "bar": str(rng.randint(58000, 92000))},
        "judge": rng.choice(["WALTER B. CROSSLAND", "MIRIAM T. FOLEY",
                             "HAROLD J. BIANCHI"]),
        "approval_date": f"{ {'February': 'March', 'March': 'April', 'April': 'May'}[exec_month] } "
                         f"{rng.randint(4, 26)}, 1987",
        "equalization": rng.randint(12, 24) * 5000,
        "apn": f"0{rng.randint(30, 58)}-{rng.randint(100, 399)}-0{rng.randint(10, 89)}",
        "acreage": rng.randint(46, 94),
        "crop_loan": rng.randint(24, 60) * 5000,
    }


# ---------------------------------------------------------------------------
# Composition — logical lines for the pleading paper
# ---------------------------------------------------------------------------

def _wrap(text: str, width: int = CHARS, indent: int = 5) -> list[str]:
    words, out, line = text.split(), [], " " * indent
    for w in words:
        cand = (line + " " + w) if line.strip() else line + w
        if len(cand) > width and line.strip():
            out.append(line)
            line = w
        else:
            line = cand
    if line.strip():
        out.append(line)
    return out


def compose_msa(m: dict, defect: dict | None = None) -> list[dict]:
    """The settlement packet as logical numbered-paper lines: the enriched
    MSA (recitals with the professional record, initialed access waiver,
    protective covenants, sealing, intermediary mechanics), property
    exhibits A-E, and the court's Order Approving with special findings.
    The strategy is to lean INTO the extremity: every professional in the
    document acknowledges the arrangement is extraordinary and builds the
    record that makes a 1987 judge's reluctant approval plausible."""
    defect = defect or {}
    dob_a = m["dob"]
    dob_b = defect.get("dob_twin_b", m["dob"])
    marriage = defect.get("marriage_date", m["marriage_date"])

    L: list[dict] = []

    def t(s=""):
        L.append({"text": s})

    def c(s):
        L.append({"text": s, "center": True})

    def para(s):
        for ln in _wrap(s):
            t(ln)

    def newpage():
        while len(L) % N_LINES:
            t()

    def sig(who, name_line, date=None):
        L.append({"text": "", "sig": who})
        t("_" * 34 + (f"          Dated: {date}" if date else ""))
        t(name_line)
        t()

    hc, wc, mc = m["husband_counsel"], m["wife_counsel"], m["minors_counsel"]

    # ---- caption -------------------------------------------------------
    for ln in (f"{hc['name']} (State Bar No. {hc['bar']})", hc["firm"],
               *hc["addr"], f"Telephone: {hc['phone']}",
               "Attorneys for Respondent NICHOLAS PARKER", ""):
        t(ln)
    c("SUPERIOR COURT OF THE STATE OF CALIFORNIA")
    c(f"COUNTY OF {m['court_county']}")
    t()
    cap = [("In re the Marriage of:", ""),
           ("", f"No. {m['case_no']}"),
           (f"Petitioner:  {m['wife']},", ""),
           ("", "MARITAL SETTLEMENT"),
           ("     and", "AGREEMENT"),
           ("", ""),
           (f"Respondent:  {m['husband']}.", "(Portions Lodged Under Seal)")]
    for left, right in cap:
        t(f"{left:<42})   {right}")
    t("_" * 42 + ")")
    t()

    para(f"THIS AGREEMENT is made and entered into at {m['forum_city']}, as of "
         f"{m['execution_date']}, by and between {m['wife']} "
         f"(\"Wife\") and {m['husband']} (\"Husband\").")
    t()
    c("R E C I T A L S")
    t()
    para(f"A.  The parties were married on {marriage} aboard "
         f"{m['married_aboard']}, and ever since said date have been and now "
         f"are Husband and Wife.")
    para(f"B.  There are two minor children of the marriage, twin daughters: "
         f"{m['twin_a']}, born {dob_a}, and {m['twin_b']}, born {dob_b}.")
    para(f"C.  Unhappy and irreconcilable differences have arisen between "
         f"the parties, by reason of which they separated on and have lived "
         f"separate and apart since {m['separation_date']}, and they intend "
         f"to live separate and apart permanently.")
    para(f"D.  Wife is a {m['wife_trade']} and intends to re-establish her "
         f"residence and the conduct of her trade at {m['wife_city']}. "
         f"Husband is the owner and operator of {m['ranch']}, where he "
         f"resides.  Each party is independently and fully capable, "
         f"financially and otherwise, of maintaining a stable home for one "
         f"child.")
    para("E.  Each party has made to the other a full and complete "
         "disclosure of all property, assets, obligations and income, and "
         "each is represented by independent counsel of his or her own "
         "choosing.")
    para("F.  The parties desire by this Agreement to settle finally all of "
         "their respective rights and obligations, including the custody "
         "and support of the minor children, all rights to support, and "
         "the division of all property.")
    para("G.  During the period immediately following separation, the "
         "parties attempted informal arrangements for shared care of the "
         "minor children.  Those attempts resulted in repeated conflict "
         "between the parties, disruption of the children's routines, and "
         "concern among the parties' physicians and advisers that continued "
         "interchange between the households would expose the children to "
         "persistent instability.")
    para(f"H.  {m['psychiatrist']}, a physician specializing in child "
         f"psychiatry, has advised the parties that, because of the infancy "
         f"of the children, their separate primary attachments, the extreme "
         f"geographical distance contemplated between the households, and "
         f"the parties' demonstrated inability to communicate without "
         f"substantial conflict, the establishment of two stable and wholly "
         f"independent households is preferable to recurrent removals, "
         f"divided loyalties and continuing parental discord.  The written "
         f"recommendation of {m['psychiatrist']} is lodged with the Court "
         f"under seal as Exhibit E hereto.")
    para("I.  The parties intend that the arrangement provided herein "
         "prevent either child from being made an instrument of the "
         "parties' conflict, and each enters into it upon professional "
         "advice and after consideration of the alternatives.")
    t()
    c("AGREEMENT")
    t()
    para("1.  DISSOLUTION.  Irreconcilable differences have caused the "
         "irremediable breakdown of the marriage within the meaning of "
         "Civil Code section 4506, and either party may proceed to judgment "
         "of dissolution upon that ground.  This Agreement shall be "
         "presented to the Court for approval and shall be incorporated in "
         "and merged with any judgment of dissolution entered in the "
         "above-entitled proceeding.")
    para(f"2.  PERMANENT DIVISION OF CUSTODY.  Subject to approval of the "
         f"Court and pursuant to Civil Code sections 4600 and 4600.5, "
         f"Husband shall have the exclusive legal and physical custody of "
         f"{m['twin_a']}, and Wife shall have the exclusive legal and "
         f"physical custody of {m['twin_b']}.  Each parent shall possess, "
         f"with respect to the child committed to his or her custody, the "
         f"sole and exclusive authority to determine residence, education, "
         f"medical care, religious upbringing, travel and all other matters "
         f"affecting that child.")
    para("The parties acknowledge that the division of the twin children "
         "between their respective households is exceptional and has been "
         "selected only after consideration of the alternatives, "
         "consultation with independent counsel and professional advisers, "
         "and determination that the preservation of two stable and "
         "independent homes outweighs the disadvantages inherent in "
         "separating the children.")
    para("3.  WAIVER OF PARENTAL ACCESS.  Except as expressly provided "
         "herein, each party knowingly and permanently relinquishes all "
         "rights of visitation, temporary custody, access, correspondence, "
         "telephone communication and other contact with the child "
         "committed to the custody of the other.  Each party acknowledges "
         "that this relinquishment is material to the entire settlement, "
         "that the other party would not have entered into this Agreement "
         "without it, and that each has been separately advised that a "
         "court ordinarily favors continuing contact between a child and "
         "both parents.")
    L.append({"text": "     Wife's Initials: ______"
              "          Husband's Initials: ______", "init": True})
    t()
    para("4.  PROTECTIVE NON-DISCLOSURE.  Until each child attains the age "
         "of eighteen years, neither party shall disclose, directly or "
         "indirectly, to the child in his or her custody:")
    para("(a) the existence or identity of the child's twin sister;")
    para("(b) the identity, residence or circumstances of the other parent;")
    para("(c) the existence or substance of this Agreement; or")
    para("(d) any fact reasonably calculated to lead the child to discover "
         "the other household.")
    para("The parties represent that premature disclosure would undermine "
         "the stability and permanence upon which the custodial arrangement "
         "depends and would expose the children to divided loyalties, "
         "transatlantic custody conflict and emotional disturbance.  "
         "Without limiting the foregoing, neither party shall permit the "
         "child in his or her custody to possess photographs of the other "
         "child or parent; neither party shall permit correspondence "
         "between the households; school, medical and passport records of "
         "each child shall be maintained wholly separately; and each party "
         "shall so instruct all household employees and relatives having "
         "contact with the child in that party's custody.  Breach of this "
         "paragraph shall entitle the non-breaching party to immediate "
         "injunctive relief.")
    para("5.  CONFIDENTIALITY AND SEALING.  The parties shall jointly "
         "request that all declarations, medical reports, custody "
         "evaluations and portions of this Agreement concerning the "
         "identity and division of the minor children be maintained under "
         "seal.  Neither party, nor any counsel, employee, relative or "
         "agent, shall disclose the terms hereof except as necessary for "
         "enforcement, immigration, medical treatment or compliance with "
         "law.  In dealings with schools, physicians and passport "
         "authorities each party shall use a certified extract of the "
         "judgment omitting reference to the other child and the other "
         "household.")
    para("6.  COMMUNICATIONS; ANNUAL CERTIFICATION.  All communications "
         "between the parties shall be transmitted through their "
         "respective attorneys of record.  Should either attorney cease "
         "practice, communications shall be transmitted through a trust "
         "officer or other neutral intermediary designated by that "
         "party's counsel.  On each anniversary of this Agreement, each "
         "party shall cause counsel to deliver to the other party's "
         "counsel written confirmation that the child in that party's "
         "custody is living, in reasonable health and enrolled in school, "
         "without photographs, residential particulars or information "
         "sufficient to locate the child.")
    para(f"7.  SURNAME.  From and after the entry of judgment herein, Wife "
         f"shall be restored her maiden surname, {m['wife_maiden']}, and "
         f"the minor child {m['twin_b']} shall thereafter be known and "
         f"enrolled in all records as {m['twin_b_new']}.")
    para("8.  ALLOCATION OF CHILD SUPPORT.  The parties acknowledge that "
         "each is financially able to provide fully for the child "
         "committed to his or her custody and that the anticipated "
         "expenses of the two children are substantially equal.  "
         "Accordingly, each party shall satisfy his or her entire support "
         "obligation by direct payment of the expenses of the child "
         "residing with that party, and no periodic payment shall be made "
         "by either party to the other.  This allocation is an integral "
         "and nonseverable element of the division of custody and property "
         "provided herein.")
    para("9.  SPOUSAL SUPPORT.  Each party waives, now and forever, any "
         "right to receive support or maintenance from the other, and the "
         "Court shall retain no jurisdiction to award spousal support to "
         "either party at any time.")
    para(f"10. REMOVAL TO ENGLAND; JURISDICTION.  Husband expressly "
         f"consents to the permanent removal of the minor child "
         f"{m['twin_b_new']} from the United States and acknowledges that "
         f"such removal is not temporary, conditional or undertaken for "
         f"purposes of visitation.  Husband waives any demand that the "
         f"child be returned to California and shall execute all passport, "
         f"immigration and travel documents reasonably required to "
         f"establish the child's permanent residence with Wife at "
         f"{m['wife_addr']}.  Wife shall have exclusive authority over the "
         f"child's travel.  The parties acknowledge the provisions of the "
         f"Uniform Child Custody Jurisdiction Act, Civil Code sections "
         f"5150 et seq., agree that the judgment herein may be established "
         f"as a custody judgment in {m['wife_forum']}, and waive all "
         f"objections founded upon distance or inconvenience of forum.  "
         f"Each party shall bear the expense of counsel in his or her own "
         f"jurisdiction.")
    para(f"11. DIVISION OF PROPERTY.  The property of the parties is "
         f"divided and confirmed as set forth in Exhibits A through D "
         f"attached hereto and incorporated herein: to Husband, the real "
         f"property and ranch operations described in Exhibit A, "
         f"principally {m['ranch']}, acquired by Husband before the "
         f"marriage and confirmed as his separate property; to Wife, the "
         f"business and trade assets described in Exhibit B, acquired by "
         f"Wife before the marriage and confirmed as her separate "
         f"property; the obligations described in Exhibit C are allocated "
         f"as there stated; and the tangible personal property described "
         f"in Exhibit D is divided as there stated.  As an equalizing "
         f"payment upon the community estate, Husband shall pay Wife the "
         f"sum of ${m['equalization']:,} within ninety (90) days of entry "
         f"of judgment.")
    para("12. ENFORCEMENT; REMEDIES.  A breach of the custody, access, "
         "non-disclosure or non-contact provisions of this Agreement shall "
         "constitute irreparable injury for which damages would be "
         "inadequate.  The non-breaching party shall be entitled to "
         "injunctive relief, attorney fees, and such modification of "
         "custody as may be necessary to restore the separate and stable "
         "household arrangement contemplated herein.  A willful attempt by "
         "either party to contact or remove the child in the custody of "
         "the other shall constitute consent to immediate suspension of "
         "the breaching party's rights hereunder as to both children "
         "pending further order of the Court.")
    para("13. INTEGRATION.  This Agreement contains the entire agreement "
         "of the parties, supersedes all prior negotiations and "
         "agreements, and may be amended only by a writing signed by both "
         "parties.  It shall be construed under the laws of the State of "
         "California.")
    t()
    para("IN WITNESS WHEREOF, the parties have executed this Agreement at "
         f"{m['forum_city']}, as of the date first written above.")
    t()
    sig("wife", f"{m['wife']}, Wife", date=m["execution_date"])
    sig("husband", f"{m['husband']}, Husband", date=m["execution_date"])
    t("APPROVED AS TO FORM:")
    t()
    sig("hcounsel", f"{hc['name']}, Attorney for Respondent")
    sig("wcounsel", f"{wc['name']}, Attorney for Petitioner")
    para(f"Reviewed solely with respect to the interests of the minor "
         f"children:")
    t()
    sig("mcounsel", f"{mc['name']} (State Bar No. {mc['bar']}),")
    t("     Attorney Appointed for the Minor Children")
    t()
    c("ACKNOWLEDGMENT")
    t()
    para(f"STATE OF CALIFORNIA, COUNTY OF {m['court_county']}.  On "
         f"{m['execution_date']}, "
         f"before me, the undersigned, a Notary Public in and for said "
         f"County and State, personally appeared {m['wife']} and "
         f"{m['husband']}, known to me to be the persons whose names are "
         f"subscribed to the within instrument, and acknowledged that they "
         f"executed the same.")
    t()
    sig("notary", f"{m['notary']['name']}, Notary Public")
    t(f"     My commission expires {m['notary']['expires']}.")

    # ---- exhibits ------------------------------------------------------
    exhibits = [
        ("A", "REAL PROPERTY AND RANCH OPERATIONS CONFIRMED TO HUSBAND", [
            f"1.  {m['ranch'].capitalize()}, Assessor's Parcel No. "
            f"{m['apn']}, approximately {m['acreage']} acres of planted "
            f"vineyard, together with the residence, barns, winery "
            f"buildings and appurtenances thereon.",
            "2.  All farm and winery equipment, including crush, tank and "
            "cooperage inventory, tractors and implements of husbandry.",
            "3.  All crops, harvested and growing, and all winery "
            "inventory in barrel and bottle.",
            "4.  All livestock and ranch vehicles."]),
        ("B", "BUSINESS AND TRADE ASSETS CONFIRMED TO WIFE", [
            "1.  The goodwill, trade name, designs, patterns, samples and "
            f"workroom equipment of Wife's business as a "
            f"{m['wife_trade']}.",
            "2.  All accounts and deposits maintained in Wife's name.",
            "3.  Wife's jewelry and articles of personal adornment."]),
        ("C", "OBLIGATIONS AND TAX LIABILITIES", [
            f"1.  The crop and operating loan of approximately "
            f"${m['crop_loan']:,} secured by Exhibit A collateral shall "
            f"be assumed and paid by Husband.",
            "2.  Obligations of Wife's business shall be assumed and paid "
            "by Wife.",
            "3.  Liability upon the parties' joint income tax return for "
            "1986 shall be borne equally; each party shall bear the tax "
            "upon his or her separate income thereafter."]),
        ("D", "TANGIBLE PERSONAL PROPERTY", [
            f"1.  Household furnishings at the {m['residence_short']} residence "
            f"are confirmed to Husband; articles shipped to "
            f"{m['wife_city']} at Wife's direction are confirmed to Wife.",
            "2.  Each party is confirmed the automobile in his or her "
            "possession.",
            "3.  The photographs and mementos of the parties have been "
            "divided between them as the parties have privately agreed."]),
    ]
    for label, title, items in exhibits:
        newpage()
        c(f"EXHIBIT {label}")
        c(title)
        t()
        for item in items:
            para(item)
            t()
    newpage()
    c("EXHIBIT E")
    c("CONFIDENTIAL CUSTODY RECOMMENDATION")
    t()
    para(f"The written recommendation of {m['psychiatrist']} concerning "
         f"the custodial arrangement for the minor children is LODGED "
         f"UNDER SEAL with the Clerk of the above-entitled Court and is "
         f"not attached to circulating copies of this Agreement.")

    # ---- order approving ----------------------------------------------
    newpage()
    L.append({"text": "", "stamp": ["FILED", _stamp_date(m["approval_date"]),
                                    f"{m['court_county']} COUNTY", "SUPERIOR COURT"]})
    c("SUPERIOR COURT OF THE STATE OF CALIFORNIA")
    c(f"COUNTY OF {m['court_county']}")
    t()
    cap2 = [("In re the Marriage of:", ""),
            ("", f"No. {m['case_no']}"),
            (f"Petitioner:  {m['wife']},", ""),
            ("", "ORDER APPROVING MARITAL"),
            ("     and", "SETTLEMENT AGREEMENT AND"),
            ("", "DIVIDING CUSTODY OF"),
            (f"Respondent:  {m['husband']}.", "MINOR CHILDREN"),
            ("", "(Portions Sealed)")]
    for left, right in cap2:
        t(f"{left:<42})   {right}")
    t("_" * 42 + ")")
    t()
    para(f"The Marital Settlement Agreement of the parties dated "
         f"{m['execution_date']} came on regularly before the undersigned. "
         f"{hc['name']} appeared for Respondent; {wc['name']} appeared for "
         f"Petitioner; {mc['name']} appeared as attorney for the minor "
         f"children.  The Court has reviewed the declarations of the "
         f"parties, the representations of counsel, and the confidential "
         f"recommendation of {m['psychiatrist']} lodged under seal.")
    t()
    c("SPECIAL FINDINGS CONCERNING THE MINOR CHILDREN")
    t()
    para("The Court finds:  (1) each party is a fit and proper parent; "
         "(2) the Agreement is not the product of coercion, and each "
         "party has had the advice of independent counsel; (3) the "
         "division of the custody of the twin children between the "
         "parties' households is extraordinary; (4) by reason of the "
         "acrimony between the parties, the age of the children, and the "
         "transatlantic separation of the households, conventional joint "
         "custody and visitation are not practicable in this case; "
         "(5) the immediate establishment of two stable, wholly "
         "independent households is necessary to the welfare of the "
         "children; (6) upon the peculiar facts established by the "
         "declarations, the professional recommendation and the "
         "representations of independent counsel, enforcement of the "
         "Agreement presently serves the welfare of the children; and "
         "(7) the Court retains jurisdiction concerning the custody of "
         "the minor children as provided by law, the intention of the "
         "parties respecting finality notwithstanding.")
    t()
    para("IT IS ORDERED, ADJUDGED AND DECREED that the Marital Settlement "
         "Agreement is approved; that its provisions, including "
         "paragraphs 2 through 10 thereof, are specifically approved and "
         "the parties ordered to comply therewith; that the declarations, "
         "medical reports and custody materials filed or lodged herein, "
         "including Exhibit E, shall be maintained UNDER SEAL and opened "
         "only upon order of this Court; and that the Clerk shall issue "
         "upon request of either party a certified extract of the "
         "judgment omitting reference to the minor child not in that "
         "party's custody.")
    t()
    t(f"Dated: {m['approval_date']}")
    t()
    sig("judge", f"HON. {m['judge']}", date=None)
    t("     JUDGE OF THE SUPERIOR COURT")
    return L


def _stamp_date(d: str) -> str:
    """'March 20, 1987' -> 'MAR 20 1987' for the clerk's stamp."""
    mon, day, year = d.replace(",", "").split()
    return f"{mon[:3].upper()} {day} {year}"


# ---------------------------------------------------------------------------
# Stage 1: vector pleading paper
# ---------------------------------------------------------------------------

def _title(s: str) -> str:
    t = s.title()
    return re.sub(r"\bMc(\w)", lambda m: "Mc" + m.group(1).upper(), t)


def _signers(m: dict) -> dict:
    """Who signs, with the name the pseudo-cursive engine draws from."""
    return {"wife": (61, "Elizabeth James Parker"),
            "husband": (62, "Nicholas Parker"),
            "hcounsel": (63, _title(m["husband_counsel"]["name"])),
            "wcounsel": (64, _title(m["wife_counsel"]["name"])),
            "notary": (65, _title(m["notary"]["name"])),
            "mcounsel": (66, _title(m["minors_counsel"]["name"])),
            "judge": (67, _title(m["judge"]))}


def _typed_pdf(lines: list[dict], rng: random.Random,
               signers: dict) -> tuple[bytes, list[list[dict]]]:
    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=letter, invariant=1)
    pages: list[list[dict]] = []
    i = 0
    page_no = 1
    while i < len(lines):
        chunk = lines[i:i + N_LINES]
        pages.append(chunk)
        c.setLineWidth(0.8)
        c.line(RULE_X1, 40, RULE_X1, PAGE_H - 30)
        c.line(RULE_X2, 40, RULE_X2, PAGE_H - 30)
        for n in range(N_LINES):
            y = LINE_1_Y - n * LEADING
            c.setFont("Courier", 9)
            c.drawRightString(NUM_X, y, str(n + 1))
            if n >= len(chunk):
                continue
            ln = chunk[n]
            if ln.get("sig"):
                seed, name = signers[ln["sig"]]
                png = assets.signature_png(seed, name=name)
                ir = ImageReader(io.BytesIO(png))
                iw, ih = ir.getSize()
                sh = 48.0
                c.drawImage(ir, TEXT_X + 6, y - 16,
                            width=sh * iw / ih, height=sh, mask="auto")
                continue
            if ln.get("init"):
                # separately initialed provision: typed labels + small marks
                c.setFont(*FONT)
                c.drawString(TEXT_X, y, ln["text"])
                for x_off, (seed, initials) in ((225, (61, "E J P")),
                                                (475, (62, "N D P"))):
                    png = assets.signature_png(seed, name=initials)
                    ir = ImageReader(io.BytesIO(png))
                    iw, ih = ir.getSize()
                    ih_pt = 17.0
                    c.drawImage(ir, x_off, y - 3,
                                width=ih_pt * iw / ih, height=ih_pt,
                                mask="auto")
                continue
            if ln.get("stamp"):
                png = assets.stamp_png(11, lines=ln["stamp"])
                ir = ImageReader(io.BytesIO(png))
                iw, ih = ir.getSize()
                sw = 150.0
                c.drawImage(ir, 405, y - sw * ih / iw + 10,
                            width=sw, height=sw * ih / iw, mask="auto")
                continue
            text = ln.get("text", "")
            if not text:
                continue
            c.setFont(*FONT)
            if ln.get("center"):
                c.drawCentredString((TEXT_X + TEXT_RIGHT) / 2, y, text)
            else:
                c.drawString(TEXT_X, y, text)
        c.setFont("Courier", 9)
        c.drawCentredString(PAGE_W / 2, 34, f"- {page_no} -")
        c.showPage()
        page_no += 1
        i += N_LINES
    c.save()
    return buf.getvalue(), pages


# ---------------------------------------------------------------------------
# Stage 2: seeded scan emulation + invisible OCR layer
# ---------------------------------------------------------------------------

def render_msa(model: dict, *, metadata: dict, defect: dict | None = None,
               scan_dpi: int = 150) -> bytes:
    """Render the agreement as a period-honest scan: JPEG page images with
    the invisible OCR text layer of a Paper-Capture workflow. `metadata`
    dates the DIGITIZATION (must be in the PDF era), not the 1987 original."""
    rng = random.Random(model.get("scan_seed", 87))
    lines = compose_msa(model, defect)
    vector, pages = _typed_pdf(lines, rng, _signers(model))

    def text_layer(idx, t):
        t.setFont("Courier", 11)
        for n, ln in enumerate(pages[idx]):
            if ln.get("text"):
                t.setTextOrigin(TEXT_X, LINE_1_Y - n * LEADING)
                t.textOut(ln["text"])

    return scan.rescan(vector, rng=rng, metadata=metadata,
                       text_layer=text_layer, dpi=scan_dpi)
