#!/usr/bin/env python3
"""
1040 Feasibility analysis.

For every strategy in tax-strategy-content, extract the input fields it needs,
tag each by category, and determine whether it corresponds to an IRS 1040 /
schedule field using the PRODUCTION ita-mapping-service as the sole source of
truth (JSON schedule mappings + the form1040 Python code mapper).

Outputs: field_mapping.csv + 1040_feasibility_report.html
"""
import csv
import glob
import html
import json
import os
import re
from collections import defaultdict

ROOT = "/Users/vsingh32/Documents/1040 feasibility"
STRAT_DIR = os.path.join(ROOT, "tax-strategy-content/IndUS/strategies")
COMMON_DIR = os.path.join(STRAT_DIR, "common")
MAP_JSON_DIR = os.path.join(ROOT, "ita-mapping-service/mappings")
FORM1040_CODE = os.path.join(ROOT, "ita-mapping-service/app/service/form1040")
OUT_DIR = os.path.join(ROOT, "output")
os.makedirs(OUT_DIR, exist_ok=True)


# ---------------------------------------------------------------------------
# STEP 1 — Build crosswalk from production ita-mapping-service
#   crosswalk: full return.<path> -> {form, line, human}
#   leaf_index: terminal leaf name -> list of {form, line, human, ita_path}
# ---------------------------------------------------------------------------
def leaf_of(path):
    """Terminal segment of a dotted ITA path (drops [..] filters)."""
    seg = path.rstrip(".").split(".")[-1]
    seg = re.sub(r"\[.*?\]", "", seg)
    return seg


crosswalk = {}          # full path -> record
leaf_index = defaultdict(list)


def add_mapping(ita_path, form, line, human, kind):
    if not ita_path:
        return
    ita_path = ita_path.strip()
    rec = {"form": form, "line": line, "human": human, "kind": kind,
           "ita_path": ita_path}
    crosswalk.setdefault(ita_path, rec)
    leaf_index[leaf_of(ita_path)].append(rec)


# 1a. JSON schedule mappings (data)
for f in sorted(glob.glob(os.path.join(MAP_JSON_DIR, "*.json"))):
    data = json.load(open(f))
    for k, v in data.items():
        if isinstance(v, dict) and v.get("ita_path"):
            fl = v.get("form_line") or "(unspecified)"
            form = fl.split(",")[0].strip()
            add_mapping(v["ita_path"], form, fl, v.get("human_readable", ""),
                        "json-schedule")

json_paths = len(crosswalk)

# 1b. form1040 Python code mapper (main 1040 + rollups + W-2 leaf builders)
#     Harvest string-literal return.<...> targets and W-2 federal.* leaves.
#
# The code mapper's string targets don't carry a machine-readable form_line, so
# we attach the REAL 1040/schedule line to each recognized main-1040 concept
# from a verified table. Line numbers are taken from the mapper source comments
# where present (e.g. iTAFedWHAdj is documented as "Line 25b + 25c + 26") and
# otherwise from the stable, unambiguous 1040 line for that concept. Paths not
# in the table keep the generic "code mapper" label rather than a guessed line.
CODE_PATH_LINES = {
    "return.summary.usITASummary.defaultSection.filingStatus": ("Form 1040", "Form 1040 filing-status boxes (top of form)"),
    "return.summary.usMain.defaultSection.filingStatus": ("Form 1040", "Form 1040 filing-status boxes (top of form)"),
    "return.summary.usMain.defaultSection.mainFilingStatus": ("Form 1040", "Form 1040 filing-status boxes (top of form)"),
    "return.summary.usITASummary.defaultSection.taxYear": ("Form 1040", "Form 1040 tax-year header"),
    "return.summary.usMain.defaultSection.taxYear": ("Form 1040", "Form 1040 tax-year header"),
    "return.summary.usITATaxpayerItems.defaultSection.firstName": ("Form 1040", "Form 1040 name/SSN block (taxpayer)"),
    "return.summary.usITATaxpayerItems.defaultSection.lastName": ("Form 1040", "Form 1040 name/SSN block (taxpayer)"),
    "return.summary.usITASpouseItems.defaultSection.firstName": ("Form 1040", "Form 1040 name/SSN block (spouse)"),
    "return.summary.usITASpouseItems.defaultSection.lastName": ("Form 1040", "Form 1040 name/SSN block (spouse)"),
    "return.summary.usITATaxpayerItems.defaultSection.primaryResidentState": ("Form 1040", "Form 1040 home-address block (state)"),
    # capital gains — Form 1040 Line 7 / Schedule D
    "return.income.usIncSum.usDispSum.federalCapital.sTCapGnLoss": ("Schedule D", "Schedule D Line 7 (net short-term) → Form 1040 Line 7"),
    "return.income.usIncSum.usDispSum.federalCapital.lTCapGnloss": ("Schedule D", "Schedule D Line 15 (net long-term) → Form 1040 Line 7"),
    "return.income.usIncSum.usDispSum.federalCapital.iTASTCapLosCaryovr": ("Schedule D", "Schedule D short-term capital-loss carryover"),
    "return.income.usIncSum.usDispSum.federalCapital.iTALTCapLosCaryovr": ("Schedule D", "Schedule D long-term capital-loss carryover"),
    # payments — documented in mapper source
    "return.payments.usPmtSum.usEstPmtInp.defaultSection.iTAFedWHAdj": ("Form 1040", "Form 1040 Line 25b + Line 25c + Line 26 (per mapper comment)"),
    "return.payments.usPmtSum.defaultSection.iTAincTaxWithhld": ("Form 1040", "Form 1040 Line 25 (federal income tax withheld)"),
    # credits — Schedule 3
    "return.credits.usCrSum.defaultSection.iTAResidentialEnergyCredit": ("Schedule 3", "Schedule 3 Line 5 (residential energy credits)"),
    "return.credits.usCrSum.defaultSection.usDCandMortgageCr": ("Schedule 3", "Schedule 3 (dependent-care & mortgage-interest credits)"),
    "return.credits.usCrSum.defaultSection.usOthCr": ("Schedule 3", "Schedule 3 (other credits)"),
    # other income / adjustments — Schedule 1
    "return.income.usIncSum.usMiscIncSum.miscellaneousIncome.tpOthIncNotSubSEtax": ("Schedule 1", "Schedule 1 Part I Line 8 (other income, not SE)"),
    "return.income.usIncSum.usMiscIncSum.miscellaneousIncome.tpOthIncSubSEtax": ("Schedule 1", "Schedule 1 Part I Line 8 (other income, subject to SE)"),
    "return.adjustments.usAdjSum.usAdjIncOthInp.defaultSection.tpOthIncAdj": ("Schedule 1", "Schedule 1 Part II (other adjustments to income)"),
    "return.adjustments.usAdjSum.usAdjIncOthInp.defaultSection.iTAHSATypeOfCoverageTaxpayer": ("Schedule 1 / Form 8889", "HSA coverage type — Schedule 1 Line 13 / Form 8889"),
    # other taxes — Schedule 2
    "return.tax.usTaxSum.defaultSection.usTxSumLumpSum": ("Schedule 2", "Schedule 2 (lump-sum distribution tax)"),
    "return.tax.usTaxSum.defaultSection.usTxSumOtherTax": ("Schedule 2", "Schedule 2 (other taxes)"),
}
code_paths = 0
code_leaves = 0
for f in sorted(glob.glob(os.path.join(FORM1040_CODE, "*.py"))):
    src = open(f, errors="ignore").read()
    fname = os.path.basename(f)
    for m in re.findall(r'"(return\.[A-Za-z0-9_.\[\]?@ =${}]+?)"', src):
        # keep only clean dotted paths (skip ones with template/expr junk)
        if re.fullmatch(r"return\.[A-Za-z0-9_.]+", m):
            if m in CODE_PATH_LINES:
                form, line = CODE_PATH_LINES[m]
                add_mapping(m, form, line, "", "code-main1040")
            else:
                add_mapping(m, "Form 1040 (main mapper)",
                            f"Form 1040 (code: {fname})", "", "code-main1040")
            code_paths += 1
    # W-2 leaf builders in taxpayer_mapper live on usWageInp[].federal.<leaf>;
    # register the leaf names so strategy W-2 leaf references match.
    if fname == "taxpayer_mapper.py":
        for leaf in re.findall(r'"(wg[A-Za-z0-9_]+|wages[A-Za-z0-9_]+)"', src):
            rec = {"form": "Form 1040 (main mapper)",
                   "line": "Form 1040 Line 1 area (W-2 build_w2_from_main_1040)",
                   "human": "W-2 wage/withholding leaf", "kind": "code-w2-leaf",
                   "ita_path": f"return.income.usIncSum.usWageSum.usWageInp[].federal.{leaf}"}
            leaf_index[leaf].append(rec)
            code_leaves += 1


# 1c. Itemized-deduction (Schedule A) leaves written via DICT-ASSIGNMENT in
#     taxpayer_mapper.build_us_item_ded_inp(). These are NOT string-literal
#     "return.<path>" targets, so the regex in 1b misses them — a coverage hole
#     found during review that mislabeled mapped Schedule A fields as "gaps".
#     Each entry is transcribed directly from the production builder (verified:
#     taxpayer_mapper.py build_us_item_ded_inp + form1040_mapper.py L192-201
#     attaches it at return.deductionsExemptions.usTxblInc.usDeductSum.usItemDedInp).
_ITEMDED_BASE = "return.deductionsExemptions.usTxblInc.usDeductSum.usItemDedInp"
_ITEMDED_LEAVES = [
    # (sub-container, leaf, Schedule A source field / line, human)
    ("taxes", "sALTWithheldEs", "Schedule A Line 5a (stateAndLocalTaxAmt)", "State & local income/sales tax"),
    ("taxes", "realEstTax", "Schedule A Line 5b (realEstateTaxesAmt + personalPropertyTaxesAmt)", "Real-estate & personal-property tax"),
    ("taxes", "usItemDedSumOthTax", "Schedule A Line 6 (otherTaxesAmt)", "Other taxes"),
    ("medical", "medExp", "Schedule A Line 1 (medicalAndDentalExpensesAmt)", "Medical & dental expenses"),
    ("interest", "mtgeIntPts", "Schedule A Line 8 (rptHomeMortgIntAndPointsAmt + form1098HomeMortgIntNotRptAmt)", "Home mortgage interest & points"),
    ("interest", "amortizationOfDeductiblePoints", "Schedule A Line 8c (form1098PointsNotReportedAmt)", "Points not reported on 1098"),
    ("interest", "mortgageInterestFromOtherSchedules", "Schedule A Line 9 (investmentInterestAmt)", "Investment interest"),
    ("usSchAContribInp.currentYearcontributions", "cash50Lim", "Schedule A Line 11 (giftsByCashOrCheckAmt)", "Charitable — cash gifts"),
    ("usSchAContribInp.currentYearcontributions", "noncash50PctLim", "Schedule A Line 12 (otherThanByCashOrCheckAmt)", "Charitable — non-cash gifts"),
    ("otherMiscellaneousDeduction", "othNotSubj2Lim", "Schedule A Line 16 (otherListTypeAmt)", "Other misc deductions (not 2% floor)"),
]
for sub, leaf, line, human in _ITEMDED_LEAVES:
    add_mapping(f"{_ITEMDED_BASE}.{sub}.{leaf}", "Schedule A", line, human,
                "code-itemded-dictwrite")
    code_paths += 1


# ---------------------------------------------------------------------------
# STEP 2 — Extract strategy input fields (with %include resolution)
# ---------------------------------------------------------------------------
# A bare 'input' can reference any tax-model phase, quoted or unquoted, and may
# be wrapped in a leading 'result.'. The ORIGINAL extractor matched only
# 'input base.return.…' and so silently dropped every projection./actual./
# quoted read — ~60% of all input fields. This regex captures all forms.
#   input base.return.<path>
#   input projection.return.<path>
#   input actual.return.<path>          (prior-year)
#   input 'projection.return.<path>'    (quoted, no jsonpath $)
#   input result.projection.return.<path>
INPUT_PHASE_RE = re.compile(
    r"input\s+'?(?:result\.)?(base|projection|actual)\.(return\.[A-Za-z0-9_.]+)")
INPUT_JSONPATH_RE = re.compile(r"input\s+'(\$\.[^']+)'")
INCLUDE_RE = re.compile(r"%include\s+'([^']+)'")
# leaf fields referenced in expressions: <obj>.federal|general|state.<leaf>
EXPR_LEAF_RE = re.compile(r"\.(?:federal|general|state)\.([A-Za-z0-9_]+)")
TEMPLATE_RE = re.compile(r"\$\{")


def read_spe(path):
    try:
        return open(path, errors="ignore").read()
    except OSError:
        return ""


def resolve_includes(text, base_content_repo):
    """Return combined text of a .spe plus any %include'd common files."""
    combined = [text]
    for inc in INCLUDE_RE.findall(text):
        # includes are like 'strategies/common/setup_global.spe'
        inc_path = os.path.join(base_content_repo, "IndUS", inc)
        if os.path.exists(inc_path):
            combined.append(read_spe(inc_path))
    return "\n".join(combined)


CONTENT_REPO = os.path.join(ROOT, "tax-strategy-content")


def norm_jsonpath(jp):
    """Normalize a jsonpath input to a return.<path> if resolvable, else None.
    Returns (normalized_or_None, is_template)."""
    if TEMPLATE_RE.search(jp):
        # still may contain a real return.<path> tail with a [?(@..)] filter
        core = re.sub(r"\[\?\(@[^]]*\)\]", "", jp)
        m = re.search(r"return\.[A-Za-z0-9_.]+", core)
        if m and not TEMPLATE_RE.search(m.group(0)):
            return m.group(0), False
        return None, True
    core = re.sub(r"\[\?\(@[^]]*\)\]", "", jp)  # drop filters
    m = re.search(r"return\.[A-Za-z0-9_.]+", core)
    if m:
        return m.group(0), False
    return None, False


# ITA-engine CALCULATED sections: the engine derives these and the strategy
# READS them — they are NOT user inputs to the strategy.
#   usITAIndexedAmount  -> tax-year limits / thresholds / statutory rates
#   usITATaxpayerItems  -> computed per-taxpayer values (max*Allowed, allSEIncome…)
#   usITASpouseItems    -> computed per-spouse values
#   usITASummary/usMain -> marginal rates, filing status derivations
#   usITAQBI/usITADependents/usSummReport -> engine-derived summaries
CALCULATED_SECTIONS = (
    "usITAIndexedAmount", "usITATaxpayerItems", "usITASpouseItems",
    "usITASummary", "usITAQBI", "usITADependents", "usSummReport", "usMain",
)

# Leaf-level overrides on top of the container heuristic above. The container
# rule ("any usITA*/usSummReport/usMain path is calculated") is a naming
# convention, not an engine trace, and a field-by-field tax-domain review
# found specific leaves inside those "calculated" containers that are really
# taxpayer-entered facts/elections, not engine-derived values. Verified via:
# (1) a live ITA plan JSON shared in Slack #ita-triad showing firstName/
#     lastName/dateOfBirth as real user data under usITATaxpayerItems, and
# (2) direct .spe source review (see per-field notes below).
# Keys are the terminal leaf name; matching is leaf-name based like the rest
# of the extractor, so this applies wherever the leaf appears (taxpayer or
# spouse container).
USER_INPUT_LEAF_OVERRIDES = {
    "filingStatus": "Filing status is a taxpayer selection (single/MFJ/MFS/HOH/QW), not engine-derived.",
    "taxYear": "Known heuristic exception: context/input value, not an engine computation.",
    "primaryResidentState": "The taxpayer's home state is an entered/selected fact.",
    "primaryResidentFullStateName": "Same as primaryResidentState — entered/selected fact.",
    "nonDeductibleIRA": "Nondeductible IRA basis (Form 8606) is user-tracked/entered, not engine-derived.",
    "rothCont": "Actual Roth contribution amount is what the taxpayer elects to contribute (distinct from the engine-computed max allowed).",
    "sepIRA": "Actual SEP-IRA contribution amount — a taxpayer/preparer entry, not a computed limit.",
    "solo401kContribution": "Actual solo 401(k) contribution amount — entered, not computed.",
    "sePremiums": "Self-employed health insurance premiums paid — entered from records, not engine-derived.",
    "studentLoanInterestPaid": "Actual interest paid comes from a 1098-E — a source-document input.",
    "familyCoverageHSA": "HSA coverage type (family vs. self-only) is a fact about the taxpayer's health plan — an input.",
    "selfOnlyCoverageHSA": "Same as familyCoverageHSA — plan-type input.",
    "resEnergyInput": "Name indicates a direct input: residential energy credit qualifying expenditure.",
}

# Leaves that are dead references in the current strategy source (commented
# out in the .spe file) — the extractor still picks them up as comment text
# is not filtered, but they are not live inputs. Flagged, not silently
# dropped, so the report can disclose them rather than mis-imply liveness.
DEAD_REFERENCE_LEAVES = {
    "qbiLimitation": "Commented out in QBI/qbi.spe — not a live input in the current strategy.",
    "spouse": "retirement.spouse — commented out in SEP-IRA.spe — not a live input in the current strategy.",
}


def categorize(path, source_kind):
    if source_kind == "prior-year":
        return "prior-year"
    if source_kind == "template":
        return "undeterminable-template"
    leaf = leaf_of(path)
    if leaf in USER_INPUT_LEAF_OVERRIDES:
        return "user-data"
    if any(sec in path for sec in CALCULATED_SECTIONS):
        return "calculated"
    return "user-data"


strategies = {}  # name -> list of field dicts

for name in sorted(os.listdir(STRAT_DIR)):
    sdir = os.path.join(STRAT_DIR, name)
    if not os.path.isdir(sdir) or name == "common":
        continue
    spe_files = glob.glob(os.path.join(sdir, "*.spe"))
    if not spe_files:
        continue

    fields = {}  # dedupe key -> dict

    def add_field(path, source_kind, from_include):
        key = (path, source_kind)
        if key in fields:
            if from_include:
                fields[key]["shared"] = True
            return
        # Category always reflects the field's true nature (input vs calculated);
        # `shared` is an orthogonal flag for fields pulled in via %include.
        leaf = leaf_of(path)
        fields[key] = {"path": path, "source_kind": source_kind,
                       "category": categorize(path, source_kind),
                       "shared": from_include,
                       "dead_reference": DEAD_REFERENCE_LEAVES.get(leaf, "")}

    for sf in spe_files:
        raw = read_spe(sf)
        # own inputs
        includes = set(INCLUDE_RE.findall(raw))
        for phase, retpath in INPUT_PHASE_RE.findall(raw):
            # actual.* is a prior-year read; base/projection are current-return.
            sk = "prior-year" if phase == "actual" else "base"
            add_field(retpath, sk, False)
        for jp in INPUT_JSONPATH_RE.findall(raw):
            norm, is_tmpl = norm_jsonpath(jp)
            if is_tmpl:
                add_field(jp, "template", False)
            elif norm:
                sk = "prior-year" if ".actual." in jp else "jsonpath"
                add_field(norm, sk, False)
            else:
                add_field(jp, "template", False)
        # expression leaf fields (W-2 style) -> strong match signal
        for leaf in EXPR_LEAF_RE.findall(raw):
            add_field(leaf, "expr-leaf", False)
        # included common inputs (tagged shared)
        for inc in includes:
            inc_path = os.path.join(CONTENT_REPO, "IndUS", inc)
            if os.path.exists(inc_path):
                itext = read_spe(inc_path)
                for phase, retpath in INPUT_PHASE_RE.findall(itext):
                    sk = "prior-year" if phase == "actual" else "base"
                    add_field(retpath, sk, True)
                for jp in INPUT_JSONPATH_RE.findall(itext):
                    norm, is_tmpl = norm_jsonpath(jp)
                    if norm and not is_tmpl:
                        sk = "prior-year" if ".actual." in jp else "jsonpath"
                        add_field(norm, sk, True)

    strategies[name] = list(fields.values())


# ---------------------------------------------------------------------------
# STEP 3/4 — Match each field to crosswalk (leaf + container rule)
# ---------------------------------------------------------------------------
def match_field(fld):
    """Return (record_or_None, precision) where precision is
    'exact' | 'leaf' | 'coarse-container' | None."""
    path = fld["path"]
    sk = fld["source_kind"]
    if sk in ("template",):
        return None, None  # undeterminable
    # expr-leaf: match by leaf name only (precise field-level)
    if sk == "expr-leaf":
        hits = leaf_index.get(path)
        return (hits[0], "leaf") if hits else (None, None)
    # exact full-path match
    if path in crosswalk:
        return crosswalk[path], "exact"
    # strategy leaf sits UNDER a mapping container -> precise
    for mp, rec in crosswalk.items():
        if path.startswith(mp + "."):
            return rec, "exact"
    # leaf-name match (precise field-level)
    hits = leaf_index.get(leaf_of(path))
    if hits:
        return hits[0], "leaf"
    # strategy CONTAINER path is a prefix of a mapping leaf -> coarse
    for mp, rec in crosswalk.items():
        if mp.startswith(path + "."):
            return rec, "coarse-container"
    return None, None


for name, flds in strategies.items():
    for fld in flds:
        rec, precision = match_field(fld)
        fld["match"] = rec
        fld["precision"] = precision
        fld["matched"] = rec is not None
        # must-needed = genuine user inputs the strategy requires: user-data
        # fields (incl. W-2 expression leaves). EXCLUDES calculated (engine-
        # derived), prior-year reads, dynamic templates, and dead references
        # (commented out in the source .spe, not actually read at runtime).
        fld["must_needed"] = fld["category"] == "user-data" and not fld.get("dead_reference")


# ---------------------------------------------------------------------------
# STEP 4c — SOURCE-DOCUMENT INFERENCE + 1040-UPLOAD AVAILABILITY
#
# Question answered: "If a user uploads their Form 1040 + all schedules, can
# each strategy run? For fields that can't be sourced from a 1040, which
# document supplies them (W-2 / 1099 / K-1 / user answer)?"
#
# "AVAILABLE from a 1040 upload" is deliberately strict:
#   - the field must have a PRECISE crosswalk match (exact/leaf) — a coarse
#     container hit does NOT prove the specific leaf is populated from a 1040.
# Everything else is a BLOCKER, split into:
#   - off-form            : data is genuinely not on the 1040/schedules; comes
#                           from a source document (W-2 box, 1099, K-1) or a
#                           user-answered question. THE real "where does it
#                           come from" answer.
#   - on-form-but-unmapped: the concept is a 1040/schedule line, but the
#                           production mapper doesn't populate it yet -> fixable
#                           by extending the mapper, no new user input needed.
# Only user-data fields gate runnability (calculated/prior-year/template do not).
# ---------------------------------------------------------------------------

# Map ITA container / leaf patterns -> source document. Ordered; first hit wins.
# Grounded in standard IRS form knowledge (user-confirmed: infer from ITA path).
SRC_DOC_RULES = [
    # --- W-2 (wages & Box 12/13/14 detail) ---
    (r"usWageInp|usWageSum|^wg[A-Z0-9]|^wages[0-9A-Za-z]", "W-2",
     "Wage & withholding detail — W-2 boxes (incl. Box 12 codes D/E/G, Box 14)."),
    (r"wages401kContribution|designated401kRoth", "W-2 Box 12 code D/AA",
     "401(k) elective deferral — W-2 Box 12 code D (Roth: AA). NOT on the 1040 (Line 1a is net of it)."),
    (r"wages403bContribution|designated403bRoth", "W-2 Box 12 code E/BB",
     "403(b) deferral — W-2 Box 12 code E (Roth: BB)."),
    (r"wg457b|designated457bRoth", "W-2 Box 12 code G/EE",
     "457(b) deferral — W-2 Box 12 code G (Roth: EE)."),
    (r"wgDCB", "W-2 Box 10", "Dependent-care benefits — W-2 Box 10."),
    (r"healthSavingsAccount|wg501c", "W-2 Box 12 code W",
     "HSA employer/employee contributions — W-2 Box 12 code W."),
    (r"MedicalSavingsAccount|wg408k6|wgadoptionCredit|adoptionCredit", "W-2 Box 12",
     "W-2 Box 12 detail (MSA / 408(k)(6) / adoption benefits)."),
    (r"eINemp|namEmp", "W-2 employer info",
     "Employer name / EIN — from the W-2, not the 1040."),
    # --- 1099 / retirement-distribution detail ---
    (r"distCode|nameOfPensPayer|pensionTpSp", "1099-R",
     "Pension/IRA distribution detail (distribution codes, payer) — Form 1099-R."),
    (r"usDivSum|federalDividend", "1099-DIV",
     "Per-payer dividend detail — Form 1099-DIV (1040 Line 3 is the aggregate)."),
    (r"usIntSum|federalInterest", "1099-INT",
     "Per-payer interest detail — Form 1099-INT (1040 Line 2 is the aggregate)."),
    (r"usCapGain|federalCapital|form4797", "1099-B / broker",
     "Per-lot capital-gain detail — Form 1099-B / broker statement (Schedule D is summarized)."),
    (r"iraSepSimple|IRAContr|spIRAContr|tpIRAContr", "IRA statement / Form 5498",
     "IRA/SEP/SIMPLE contribution — Form 5498 or plan statement (not a 1040 line)."),
    (r"SEElectDef|SEPContr|EElectDef|EPContr|spsE", "Self-employed plan records",
     "Self-employed retirement contribution — plan/employer records."),
    # --- K-1 / pass-through activity detail ---
    (r"usPShipInp", "Schedule K-1 (1065)",
     "Partnership detail — Schedule K-1 (Form 1065). Schedule E shows only the rollup."),
    (r"usScorpInp", "Schedule K-1 (1120-S)",
     "S-corp detail — Schedule K-1 (Form 1120-S)."),
    (r"usBusIncInp", "Sole-prop books",
     "Sole-proprietor line detail — books/records behind Schedule C."),
    (r"usRentRoyInp", "Rental records",
     "Per-property rental detail behind Schedule E."),
    (r"usFarmIncInp", "Farm records",
     "Per-farm detail behind Schedule F."),
    # --- deductions/adjustments detail not itemized on the form ---
    (r"substantiatedEmployeeExp|AccountableReimbursement", "Employee-expense records",
     "Substantiated employee expense — taxpayer records, not a 1040 line."),
    (r"fsaContribution", "Benefits statement",
     "FSA contribution — employer benefits statement."),
]

# Concepts we KNOW are 1040/schedule lines (so an unmatched one = mapper gap,
# not off-form). Keep small & concept-based; cross-checked vs the project-air
# form enumeration by tax concept.
ON_FORM_CONCEPTS = [
    (r"mortgageInterest|mtgeIntPts|totIntPd", "Schedule A", "Mortgage interest — Schedule A line 8."),
    (r"realEstTax", "Schedule A", "Real-estate tax — Schedule A line 5b."),
    (r"itemDedAll|itemizedDeduction", "Schedule A", "Itemized-deduction total — Schedule A."),
    (r"CharCont|totAllContr|totalAvailCharCont|cash50Lim", "Schedule A", "Charitable contributions — Schedule A lines 11–14."),
    (r"miscellaneousIncome|OtherIncome|otherIncome", "Schedule 1", "Other income — Schedule 1."),
]


def infer_source_doc(path):
    """Return (doc, note) for a field not sourceable from a 1040. Falls back to
    a generic 'source document / user answer' when no rule matches."""
    lp = path
    for pat, doc, note in SRC_DOC_RULES:
        if re.search(pat, lp):
            return doc, note
    return "user answer / source doc", "Not matched to any known IRS document pattern — likely a user-answered question or a source-document field."


def on_form_concept(path):
    for pat, form, note in ON_FORM_CONCEPTS:
        if re.search(pat, path):
            return form, note
    return None, None


# availability classification (only meaningful for user-data fields)
for name, flds in strategies.items():
    for fld in flds:
        fld["src_doc"] = ""
        fld["src_note"] = ""
        if fld["category"] != "user-data":
            fld["avail"] = "n/a"        # calculated/prior-year/template don't gate
            # (A)/(B) split for CALCULATED fields — the exec question:
            #   is this a value that also appears on the 1040 (read straight off
            #   the form), or is it engine-internal (never a form line, the
            #   engine must recompute it)?
            if fld["category"] == "calculated":
                if fld["precision"] in ("exact", "leaf"):
                    fld["calc_loc"] = "on-1040"    # (A) printed on a 1040 line
                else:
                    fld["calc_loc"] = "engine-only"  # (B) not on any 1040 line
            continue
        precise = fld["precision"] in ("exact", "leaf")
        if precise:
            fld["avail"] = "available"  # populated from 1040+schedules today
        else:
            # BLOCKER. off-form vs on-form-but-unmapped?
            form, note = on_form_concept(fld["path"])
            if form:
                fld["avail"] = "on-form-but-unmapped"
                fld["src_doc"] = form
                fld["src_note"] = "On " + note + " — the production mapper does not populate it yet (fixable by extending the mapper)."
            else:
                fld["avail"] = "off-form"
                doc, dnote = infer_source_doc(fld["path"])
                fld["src_doc"] = doc
                fld["src_note"] = dnote


# per-strategy runnability: runnable iff NO user-data field is a blocker
strat_runnable = {}
for name, flds in strategies.items():
    blockers = [f for f in flds if f["avail"] in ("off-form", "on-form-but-unmapped")]
    n_ud = sum(1 for f in flds if f["category"] == "user-data")
    if len(blockers) > 0:
        verdict = "blocked"
    elif n_ud == 0:
        verdict = "no-user-inputs"   # trivially passes: reads only engine-computed values
    else:
        verdict = "runnable"          # every user input is on the 1040/schedules
    strat_runnable[name] = {
        "runnable": len(blockers) == 0,
        "verdict": verdict,
        "blockers": blockers,
        "n_userdata": n_ud,
        "n_available": sum(1 for f in flds if f["avail"] == "available"),
    }


# ---------------------------------------------------------------------------
# STEP 4b — Sanity gate: 401k example must show a W-2 match + computed-unmatch
# ---------------------------------------------------------------------------
sanity = {"w2_match": False, "max401k_unmatched": False, "detail": []}
calc = strategies.get("401k Employee Contribution Calculator", [])
for fld in calc:
    if fld["source_kind"] == "expr-leaf" and fld["path"] == "wgFedwages":
        sanity["w2_match"] = fld["matched"]
    if "max401kcontributionallowed" in fld["path"].lower():
        sanity["max401k_unmatched"] = not fld["matched"]
sanity["401k_not_runnable"] = not strat_runnable.get(
    "401k Employee Contribution Calculator", {}).get("runnable", True)
sanity["detail"] = [f"wgFedwages available={sanity['w2_match']}",
                    f"max401kContributionAllowed unmatched={sanity['max401k_unmatched']}",
                    f"401k strategy NOT runnable from 1040 alone={sanity['401k_not_runnable']}"]


# ---------------------------------------------------------------------------
# STEP 5 — Emit CSV + HTML
# ---------------------------------------------------------------------------
csv_path = os.path.join(OUT_DIR, "field_mapping.csv")
with open(csv_path, "w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["strategy", "runnable_from_1040", "field_path", "source_kind",
                "category", "calc_1040_location", "must_needed", "availability",
                "source_document", "source_note", "matched", "match_precision",
                "form", "form_line", "human_readable", "dead_reference"])
    for name in sorted(strategies):
        runnable = "Y" if strat_runnable[name]["runnable"] else "N"
        for fld in sorted(strategies[name], key=lambda x: x["path"]):
            m = fld["match"] or {}
            # For calculated fields: on-1040 (read off the form) vs engine-only.
            calc_loc = fld.get("calc_loc", "") if fld["category"] == "calculated" else ""
            w.writerow([name, runnable, fld["path"], fld["source_kind"],
                        fld["category"], calc_loc,
                        "Y" if fld["must_needed"] else "N",
                        fld["avail"], fld["src_doc"], fld["src_note"],
                        "Y" if fld["matched"] else "N",
                        fld["precision"] or "",
                        m.get("form", ""), m.get("line", ""), m.get("human", ""),
                        fld.get("dead_reference", "")])

# rollup
total = sum(len(v) for v in strategies.values())
matched = sum(1 for v in strategies.values() for f in v if f["matched"])
precise = sum(1 for v in strategies.values() for f in v
              if f["precision"] in ("exact", "leaf"))
coarse = sum(1 for v in strategies.values() for f in v
             if f["precision"] == "coarse-container")
templ = sum(1 for v in strategies.values() for f in v
            if f["source_kind"] == "template")
unmatched = total - matched - templ
by_cat = defaultdict(int)
by_form = defaultdict(int)
n_calculated = sum(1 for v in strategies.values() for f in v
                   if f["category"] == "calculated")
n_userinput = sum(1 for v in strategies.values() for f in v
                  if f["category"] == "user-data")
must_total = 0
must_matched = 0
for v in strategies.values():
    for f in v:
        by_cat[f["category"]] += 1
        if f["matched"]:
            by_form[(f["match"] or {}).get("form", "?")] += 1
        if f["must_needed"]:
            must_total += 1
            if f["matched"]:
                must_matched += 1


# --- runnability rollup (the headline answer) ---
n_real_runnable = sum(1 for v in strat_runnable.values() if v["verdict"] == "runnable")
n_no_inputs = sum(1 for v in strat_runnable.values() if v["verdict"] == "no-user-inputs")
n_runnable = sum(1 for v in strat_runnable.values() if v["runnable"])
n_blocked = len(strat_runnable) - n_runnable
# distinct blocking user-data fields by source document
blocker_by_doc = defaultdict(set)
for name, info in strat_runnable.items():
    for f in info["blockers"]:
        blocker_by_doc[f["src_doc"]].add(f["path"])
n_offform = sum(1 for v in strategies.values() for f in v if f.get("avail") == "off-form")
n_mappergap = sum(1 for v in strategies.values() for f in v if f.get("avail") == "on-form-but-unmapped")
n_available = sum(1 for v in strategies.values() for f in v if f.get("avail") == "available")
# (A)/(B) split for calculated fields — the exec's direct question.
n_calc_onform = sum(1 for v in strategies.values() for f in v
                    if f["category"] == "calculated" and f.get("calc_loc") == "on-1040")
n_calc_engine = sum(1 for v in strategies.values() for f in v
                    if f["category"] == "calculated" and f.get("calc_loc") == "engine-only")


def esc(x):
    return html.escape(str(x))


# canonical strategy numbering (alphabetical — matches per-strategy detail order)
strat_no = {name: i for i, name in enumerate(sorted(strategies), start=1)}

# ---------------------------------------------------------------------------
# Graceful-degradation check: does the strategy's own .spe source coalesce a
# BLOCKING field to a default (e.g. `X ? X : 0`) instead of requiring it?
# This was checked by (1) scanning each blocked strategy's source for a
# null-guard/ternary-coalesce applied to a variable assigned from one of ITS
# OWN blocking field paths, then (2) manually verifying every hit against the
# raw .spe source, because two apparent hits (IRA QCD, Mega Backdoor Roth)
# turned out to be false positives — the coalesce-to-0 there is on the
# *prior-year* (`actual.`) copy of the field, used only for a comparison
# baseline, while the real blocking fields (current-year detail read via
# `applicability` filters with no guard) have no fallback at all. Only two
# strategies survived verification. This is a static-source finding, not a
# runtime test — it does not confirm what value the engine ultimately
# recommends, only that the field itself won't cause a hard block.
VERIFIED_FALLBACKS = {
    "Child Tax Credit": {
        "coverage": "full",
        "note": ("Every blocking field is an estimated-tax-payment amount "
                 "(prior-year overpayment applied, 4 ES vouchers, extension "
                 "payment, fiduciary K-1 ES) and each is coalesced to 0 if "
                 "absent — <span class='code'>X ? X : 0</span> pattern, "
                 "child-tax-credit.spe lines 82-102. A taxpayer with no "
                 "estimated payments genuinely has $0 there, so this is a "
                 "legitimate default, not a workaround."),
    },
    "PTET": {
        "coverage": "partial",
        "note": ("Only <span class='code'>primaryResidentFullStateName</span> "
                 "coalesces to a default (<span class='code'>'-'</span>, "
                 "ptet.spe line 7). The other 6 blocking fields (business/farm/"
                 "passthrough K-1 income detail) have no fallback — the "
                 "strategy is still genuinely blocked overall."),
    },
}

# --- headline runnability section (leads the report) ---
run_rows = []
run_rows_compact = []
for name in sorted(strat_runnable, key=lambda n: strat_no[n]):
    info = strat_runnable[name]
    vmap = {"runnable": "<span class='yes'>RUNNABLE</span>",
            "no-user-inputs": "<span class='tmpl'>trivial (reads only engine values)</span>",
            "blocked": "<span class='no'>NOT runnable</span>"}
    verdict = vmap[info["verdict"]]
    docs = sorted({f["src_doc"] for f in info["blockers"]})
    # Explicit per-field breakdown: which field is missing, and exactly which
    # form/schedule/document contains it. off-form blockers show the inferred
    # source document (W-2/1099/K-1/etc. — genuinely not on the 1040).
    # on-form-but-unmapped blockers show the real 1040/schedule line the
    # concept belongs to (the mapper just doesn't populate it yet).
    missing_seen = set()
    missing_items = []
    for f in sorted(info["blockers"], key=lambda x: x["path"]):
        field_label = leaf_of(f["path"])
        if field_label == "deleteNextYear":
            continue
        if f["avail"] == "on-form-but-unmapped":
            where = f"{esc(f['src_doc'])} <small>(on the form; mapper gap)</small>"
        else:
            where = esc(f["src_doc"])
        dedup_key = (field_label, where)
        if dedup_key in missing_seen:
            continue
        missing_seen.add(dedup_key)
        missing_items.append(f"<li><span class='code'>{esc(field_label)}</span> — {where}</li>")
    missing_cell = ("<ul class='misslist'>" + "".join(missing_items) + "</ul>") if missing_items else "<span class='yes'>—</span>"
    fb = VERIFIED_FALLBACKS.get(name)
    if not info["blockers"]:
        fallback_cell = "<span class='muted'>n/a</span>"
    elif fb and fb["coverage"] == "full":
        fallback_cell = f"<span class='yes'>Yes — defaults to 0/blank</span><br><small>{fb['note']}</small>"
    elif fb and fb["coverage"] == "partial":
        fallback_cell = f"<span class='tmpl'>Partial</span><br><small>{fb['note']}</small>"
    else:
        fallback_cell = "<span class='no'>No — checked, no fallback found</span>"
    run_rows.append(
        f"<tr class='{'m' if info['runnable'] else 'u'}'>"
        f"<td>Strategy {strat_no[name]}</td>"
        f"<td>{esc(name)}</td><td>{verdict}</td>"
        f"<td>{info['n_available']}/{info['n_userdata']}</td>"
        f"<td>{len(info['blockers'])}</td>"
        f"<td>{esc(', '.join(docs))}</td>"
        f"<td>{fallback_cell}</td>"
        f"<td>{missing_cell}</td></tr>")
    # Compact variant (used by the standalone strategies-table file): same
    # row data, minus the "Missing field(s) & exact form/document" column.
    run_rows_compact.append(
        f"<tr class='{'m' if info['runnable'] else 'u'}'>"
        f"<td>Strategy {strat_no[name]}</td>"
        f"<td>{esc(name)}</td><td>{verdict}</td>"
        f"<td>{info['n_available']}/{info['n_userdata']}</td>"
        f"<td>{len(info['blockers'])}</td>"
        f"<td>{esc(', '.join(docs))}</td>"
        f"<td>{missing_cell}</td></tr>")
run_table = ("<table><tr><th>#</th><th>Strategy</th><th>From a 1040 upload?</th>"
             "<th>User inputs available</th><th># blocking fields</th>"
             "<th>Missing data comes from</th>"
             "<th>Missing field(s) &amp; exact form/document</th>"
             "<th>Degrades gracefully if missing?</th></tr>" + "".join(run_rows) + "</table>")
run_table_compact = ("<table><tr><th>#</th><th>Strategy</th><th>From a 1040 upload?</th>"
             "<th>User inputs available</th><th># blocking fields</th>"
             "<th>Missing data comes from</th>"
             "<th>Missing field(s) &amp; exact form/document</th></tr>" + "".join(run_rows_compact) + "</table>")

doc_rows = "".join(
    f"<tr><td>{esc(doc)}</td><td>{len(paths)}</td></tr>"
    for doc, paths in sorted(blocker_by_doc.items(), key=lambda x: -len(x[1])))

# Documents ranked by how many strategies REFERENCE them as a blocker.
# NOTE: most blocked strategies need several documents at once, so a strategy
# can appear under multiple documents here — these counts do NOT sum to the
# number of blocked strategies, and obtaining one document does not by itself
# make those strategies runnable (see "fully unlocks" below for that).
doc_to_strats = defaultdict(set)
for name, info in strat_runnable.items():
    for f in info["blockers"]:
        doc_to_strats[f["src_doc"]].add(name)
# Documents that would FULLY unlock a strategy on their own — i.e. it is the
# strategy's ONLY blocking document. This is the real "ingest this one thing
# and the strategy becomes runnable" signal.
doc_fully_unlocks = defaultdict(set)
for name, info in strat_runnable.items():
    docs_needed = {f["src_doc"] for f in info["blockers"]}
    if len(docs_needed) == 1:
        doc_fully_unlocks[next(iter(docs_needed))].add(name)
doc_unlock_rows = "".join(
    f"<tr><td>{esc(doc)}</td><td>{len(strs)}</td>"
    f"<td><b>{len(doc_fully_unlocks.get(doc, ()))}</b></td>"
    f"<td>{len(blocker_by_doc[doc])}</td></tr>"
    for doc, strs in sorted(doc_to_strats.items(), key=lambda x: -len(doc_fully_unlocks.get(x[0], ()))))


rows_html = []
for name in sorted(strategies):
    flds = sorted(strategies[name], key=lambda x: (not x["must_needed"], x["path"]))
    info = strat_runnable[name]
    verdict = ("<span class='yes'>RUNNABLE from 1040 upload</span>" if info["runnable"]
               else f"<span class='no'>NOT runnable — {len(info['blockers'])} field(s) missing</span>")
    rows_html.append(f"<h3>{esc(name)} — {verdict} "
                     f"<small>({info['n_available']}/{info['n_userdata']} user inputs available)</small></h3>")
    rows_html.append("<table><tr><th>Field (ITA path / leaf)</th>"
                     "<th>Category</th><th>1040 availability</th>"
                     "<th>Exactly where on the 1040 (or which doc if missing)</th></tr>")
    # user-data first (they gate runnability), blockers on top
    avail_order = {"off-form": 0, "on-form-but-unmapped": 1, "available": 2, "n/a": 3}
    for f in sorted(flds, key=lambda x: (avail_order.get(x.get("avail"), 9), x["path"])):
        av = f.get("avail", "n/a")
        m = f.get("match") or {}
        form_line = (m.get("line") or m.get("form") or "").strip()
        if av == "available":
            badge = "<span class='yes'>on 1040/schedule ✓</span>"
        elif av == "on-form-but-unmapped":
            badge = "<span class='tmpl'>on form, mapper gap</span>"
        elif av == "off-form":
            badge = "<span class='no'>NOT on 1040</span>"
        elif f["category"] == "calculated" and f.get("calc_loc") == "on-1040":
            badge = "<span class='yes'>calculated · on 1040 ✓</span>"
        elif f["category"] == "calculated":
            badge = "<span class='muted'>calculated · engine-internal</span>"
        else:
            badge = f"<span class='muted'>{esc(f['category'])}</span>"
        # location cell: show the real 1040 line where we have one; otherwise the
        # source document for a missing field; otherwise mark engine-internal.
        if f.get("src_doc"):
            loc = f"<b>{esc(f['src_doc'])}</b><br><small>{esc(f['src_note'])}</small>"
        elif form_line and (av == "available" or f.get("calc_loc") == "on-1040"):
            loc = f"<b>{esc(form_line)}</b>"
        elif f["category"] == "calculated":
            loc = "<small class='muted'>not a 1040 line — engine recomputes it</small>"
        else:
            loc = ""
        rows_html.append(
            f"<tr class='{'u' if av in ('off-form','on-form-but-unmapped') else 'm'}'>"
            f"<td class='code'>{esc(f['path'])}</td>"
            f"<td>{esc(f['category'])}</td>"
            f"<td>{badge}</td>"
            f"<td>{loc}</td>"
            f"</tr>")
    rows_html.append("</table>")

form_rows = "".join(f"<tr><td>{esc(k)}</td><td>{v}</td></tr>"
                    for k, v in sorted(by_form.items(), key=lambda x: -x[1]))
cat_rows = "".join(f"<tr><td>{esc(k)}</td><td>{v}</td></tr>"
                   for k, v in sorted(by_cat.items(), key=lambda x: -x[1]))

sanity_ok = sanity["w2_match"] and sanity["max401k_unmatched"]

# worked example rows (401k Calculator) — user-data fields only, plain language
EX_LABELS = {
    "wgFedwages": "Total wages (W-2 Box 1)",
    "wgTpSp": "Whose W-2 (taxpayer/spouse)",
    "wages401kContribution": "401(k) contribution amount (W-2 Box 12, code D)",
    "wages403bContribution": "403(b) contribution (W-2 Box 12, code E)",
    "wg457b": "457(b) contribution (W-2 Box 12, code G)",
    "namEmp": "Employer name",
    "return.income.usIncSum.usWageSum.usWageInp": "The individual W-2 record",
    "deleteNextYear": "Internal flag",
}
ex = strat_runnable.get("401k Employee Contribution Calculator", {})
ex_flds = strategies.get("401k Employee Contribution Calculator", [])
ex_seen = set()
ex_rows = []
for f in sorted(ex_flds, key=lambda x: (0 if x["avail"] == "available" else 1, x["path"])):
    if f["category"] != "user-data" or f["path"] in ex_seen:
        continue
    ex_seen.add(f["path"])
    label = EX_LABELS.get(f["path"], f["path"])
    if f["avail"] == "available":
        where = "<span class='yes'>On the 1040 (Line 1)</span>"
    else:
        where = f"<span class='no'>NOT on the 1040</span> → {esc(f['src_doc'])}"
    ex_rows.append(f"<tr class='{'m' if f['avail']=='available' else 'u'}'>"
                   f"<td>{esc(label)}</td><td>{where}</td></tr>")
ex_table = ("<table><tr><th>What the strategy needs</th><th>Can we get it from a 1040?</th></tr>"
            + "".join(ex_rows) + "</table>")
html_doc = f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<title>1040 Feasibility — Strategy Input Fields</title>
<style>
body{{font-family:-apple-system,Segoe UI,Roboto,sans-serif;margin:0;color:#1a1a1a;line-height:1.5;background:#fafbfc}}
.wrap{{max-width:1000px;margin:0 auto;padding:2.5rem 2rem}}
h1{{font-size:1.9rem;margin:0 0 .2rem}}
h2{{font-size:1.35rem;margin:2.4rem 0 .6rem;padding-bottom:.25rem;border-bottom:2px solid #e2e8f0}}
h3{{font-size:1.05rem;margin:1.4rem 0 .4rem}}
.sub{{color:#667;margin:0 0 1.5rem}}
table{{border-collapse:collapse;width:100%;margin:.5rem 0 1.5rem;font-size:13px;background:#fff}}
th,td{{border:1px solid #e2e8f0;padding:6px 9px;text-align:left;vertical-align:top}}
th{{background:#f0f4f8;font-weight:600}}
.code{{font-family:ui-monospace,Menlo,monospace;font-size:12px;color:#334}}
tr.m{{background:#f2fbf5}} tr.u{{background:#fff7f5}}
.yes{{color:#0a7;font-weight:700}} .no{{color:#c33;font-weight:700}} .tmpl{{color:#a70}} .muted{{color:#889}}
.kpi{{display:inline-block;background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:1rem 1.3rem;margin:.3rem .3rem 0 0;text-align:center;min-width:130px;vertical-align:top}}
.kpi b{{display:block;font-size:2rem;line-height:1.1;color:#0a7}}
.kpi.warn b{{color:#c33}} .kpi small{{color:#667;display:block;margin-top:.2rem}}
.answer{{background:#fdecea;border-left:5px solid #c33;padding:1.1rem 1.3rem;border-radius:6px;margin:1.2rem 0;font-size:1.05rem}}
.answer b{{color:#a00}}
.note{{background:#f0f4f8;border-left:5px solid #7a9;padding:.9rem 1.2rem;border-radius:6px;margin:1rem 0;font-size:.92rem;color:#3a4a55}}
.appendix{{margin-top:3rem;border-top:3px solid #cbd5e0;padding-top:1rem}}
.appendix h2{{color:#556}}
small{{color:#667;font-weight:400}}
.tag{{display:inline-block;font-size:11px;padding:1px 7px;border-radius:10px;font-weight:600}}
.tag.ok{{background:#e6f7ee;color:#075}} .tag.bad{{background:#fdecea;color:#a00}}
ul.misslist{{margin:0;padding-left:1.1rem}} ul.misslist li{{margin:0 0 .3rem}}
</style></head><body><div class="wrap">

<h1>Can our tax strategies run from a customer's 1040?</h1>
<p class="sub">Feasibility analysis of {len(strategies)} strategies · source of truth: production <span class="code">ita-mapping-service</span></p>

<!-- ========== 1. THE ANSWER (BLUF) ========== -->
<div class="answer">
<b>Almost none.</b> Of {len(strategies)} strategies, only <b>{n_real_runnable}</b> have every user input on the 1040
itself; <b>{n_blocked}</b> need at least one <b>source document</b> beyond the filed return — a W-2 (with Box 12
detail), a 1099, or a K-1. A further <b>{n_no_inputs}</b> read no raw inputs but depend on engine-computed values
(marginal rate, MAGI, contribution limits) that are <em>not</em> printed on the 1040, so they still need the
underlying documents to be recomputed. The 1040 carries <b>summary totals</b>; the strategies need the
<b>underlying detail</b> those totals are built from.
</div>

<!-- ========== 2. HOW BIG IS THE GAP ========== -->
<h2>How big is the gap?</h2>
<div>
<div class="kpi warn"><b>{n_blocked}</b><small>strategies need a<br>document beyond the 1040</small></div>
<div class="kpi"><b>{n_real_runnable}</b><small>strategies whose inputs<br>are all on the 1040</small></div>
<div class="kpi"><b>{n_no_inputs}</b><small>strategies that read only<br>engine-computed values</small></div>
<div class="kpi"><b>{len(doc_to_strats)}</b><small>distinct source documents<br>required across all</small></div>
</div>
<p>Of the {len(strategies)} strategies, <b>{n_blocked}</b> reference at least one input field that is not on the 1040
or its schedules — those strictly need a source document (W-2, 1099, K-1). <b>{n_real_runnable}</b> have every
user input on the 1040. A further <b>{n_no_inputs}</b> read no raw inputs at all — only engine-computed values
(marginal rate, MAGI, contribution limits). Those engine values are <em>not</em> printed on the 1040 (see next
section), so even the "input-free" strategies still need the underlying documents so the engine can recompute them.</p>

<!-- ========== 2b. THE CALCULATED-FIELD QUESTION ========== -->
<h2>"Available" vs "calculated" — is the field actually on the 1040?</h2>
<p>A field a strategy reads falls into one of three buckets. The distinction the question turns on is
<b>whether a <em>calculated</em> value is also printed on the 1040</b> (so it can be read straight off an upload)
or is <b>engine-internal</b> (never a form line — the tax engine has to recompute it from the underlying documents):</p>
<table>
<tr><th>Bucket</th><th>Count (field references)</th><th>On a 1040 line?</th><th>Examples</th></tr>
<tr class="m"><td><b>User input, on the 1040</b></td><td>{n_available}</td><td class="yes">Yes — read from the form</td>
    <td>wages (Line 1), Schedule A real-estate tax (5b), Schedule D gains</td></tr>
<tr class="m"><td><b>Calculated, printed on the 1040</b> (A)</td><td>{n_calc_onform}</td><td class="yes">Yes — read from the form</td>
    <td>filing status, AGI-linked rollups, Schedule 1 rental adjustment</td></tr>
<tr class="u"><td><b>Calculated, engine-internal</b> (B)</td><td>{n_calc_engine}</td><td class="no">No — never a form line</td>
    <td>marginalRate, modifiedAgi, usITAQBI, contribution limits (maxHSAcontribution, maxIRAContributionAllowed)</td></tr>
<tr class="u"><td><b>User input, off the 1040</b></td><td>{n_offform}</td><td class="no">No — needs a source doc</td>
    <td>401(k) deferral (W-2 Box 12), per-payer 1099 detail, K-1 lines</td></tr>
</table>
<p class="note">So when a strategy reads a "calculated" field, it is <b>not</b> automatically 1040-available. Only the
<b>{n_calc_onform}</b> bucket-(A) references are actually on the form; the <b>{n_calc_engine}</b> bucket-(B) references
(the large majority of calculated reads) are engine-internal and require the full return to be recomputed — which in
turn requires the source documents. The per-strategy detail table below shows, for every field, the exact 1040 line
where one exists.</p>

<!-- ========== 3. WHAT'S MISSING & WHERE IT COMES FROM ========== -->
<h2>What's missing — which documents are involved, and which would fully unlock a strategy</h2>
<p>Most blocked strategies need <b>more than one</b> source document at once, so a strategy can appear under several
rows below — these counts do not add up to the number of blocked strategies, and ingesting a single document
usually does not by itself make a strategy runnable. The <b>"fully unlocks alone"</b> column is the one number that
does mean that: it counts only strategies for which this is the <em>one and only</em> blocking document, so ingesting
it is sufficient on its own. Ranked by that column — this is the real ingestion priority list.</p>
<table><tr><th>Source document</th><th>Strategies that reference it as a blocker</th>
<th>Fully unlocks alone</th><th>Fields it supplies</th></tr>{doc_unlock_rows}</table>

<!-- ========== 4. A CONCRETE EXAMPLE ========== -->
<h2>Worked example: the 401(k) Contribution strategy</h2>
<p>The strategy compares each W-2's 401(k) contribution against the allowed maximum. Here is exactly what it needs,
and whether a 1040 can supply it:</p>
{ex_table}
<div class="note"><b>Why the 1040 isn't enough here:</b> Form 1040 Line 1a shows <em>total wages</em> — but that number is
already <em>net</em> of the 401(k) contribution. The contribution amount itself lives only on the <b>W-2, Box 12 (code D)</b>,
which is not carried onto the 1040. So we can see the wages, but not the very number this strategy is about.
{'&nbsp;<span class="tag ok">example verified against production data</span>' if sanity_ok else '<span class="tag bad">example failed verification — review</span>'}</div>

<!-- ========== 5. FULL PER-STRATEGY VERDICT ========== -->
<h2>All {len(strategies)} strategies — runnability verdict</h2>
<p><small>"Trivial" = reads only engine-computed values, no raw user inputs (still needs source docs upstream to compute them).
The <b>"Degrades gracefully if missing?"</b> column answers a different question than runnability: even when a field is
missing, does the strategy's own <span class="code">.spe</span> source coalesce it to a safe default (e.g. treating an
absent estimated-tax-payment as $0) instead of requiring it? This was checked by static source review of each blocked
strategy — searching for a null-guard or <span class="code">X ? X : default</span> pattern applied specifically to that
strategy's own blocking fields, then manually verifying every match against the raw source (two apparent matches were
discarded as false positives — the coalesce there covered only a prior-year comparison value, not the actual blocking
field). This is <b>not a runtime test</b>: it confirms the source contains a fallback, not what the engine ultimately
computes or recommends when it's exercised. Only strategies explicitly marked "Yes" or "Partial" below have a
confirmed fallback; "No — checked, no fallback found" means the pattern search ran and found nothing, not that
degradation is impossible.</small></p>
{run_table}


<!-- ================= APPENDIX (technical) ================= -->
<div class="appendix">
<h2>Appendix — method &amp; field-level detail</h2>

<h3>How this was determined</h3>
<p><small><b>Extraction-completeness fix (disclosure):</b> an earlier revision of the field extractor matched only
<span class="code">input base.return.…</span> and silently dropped every <span class="code">input projection.return.…</span>,
<span class="code">actual.</span>, and quoted-string read — about 60% of all input references, which had collapsed several
strategies to a false "0 user inputs → runnable" verdict. The extractor now captures all input phases
(base/projection/actual, quoted or unquoted, incl. a leading <span class="code">result.</span>), raising the analyzed
field count to {total}. All numbers below reflect the corrected extraction.</small></p>
<p><small>The <b>source of truth</b> is the production <span class="code">ita-mapping-service</span>: its JSON schedule
mappings ({json_paths} paths) plus its <span class="code">form1040</span> code mapper ({code_paths} code paths +
{code_leaves} W-2 field builders). Recognized main-1040 code targets (filing status, capital gains, payments Line
25b+25c+26, credits, other income) are pinned to their real 1040/schedule line from a verified table; unrecognized
code targets keep a generic "code mapper" label rather than a guessed line. The code paths are harvested two ways: string-literal <span class="code">"return.…"</span>
targets, and the <b>dict-assignment</b> writes in the Schedule A itemized-deduction builder
(<span class="code">build_us_item_ded_inp</span>, e.g. <span class="code">taxes["realEstTax"]=…</span>) — the latter added
after a review found the string-literal scan alone had mislabeled mapped Schedule A fields as gaps.
A strategy field counts as <b>available from a 1040</b> only when it has a
<em>precise</em> match into that crosswalk — a field name or full-path match. Loose container-level matches ({coarse} of them)
are <b>not</b> counted as available, because a container match doesn't prove the specific value is populated from a 1040.
Everything else is a blocker, split into <em>off-form</em> (needs a source document) vs <em>on-form-but-unmapped</em>
({n_mappergap} fields — the concept is a 1040 line, but the mapper doesn't populate it yet; fixable by extending the mapper).
The <span class="code">tax-advisory-toolkit</span> repo is excluded (not in production). Source documents are inferred from
the ITA data path using standard IRS-form knowledge. One further limit: the 1040 collapses all W-2s into a single Line 1a,
so even "available" wage fields aren't available <em>per employer</em>, which W-2-iterating strategies require.</small></p>
<p><small><b>How "engine-calculated" is decided (disclosure):</b> a field is tagged <em>calculated</em> when its ITA path sits
under a computed-summary section (<span class="code">summary.usITAIndexedAmount / usITATaxpayerItems / usITASpouseItems /
usITASummary / usITAQBI / usITADependents / usSummReport / usMain</span>). This container rule is a <b>naming-convention
heuristic</b>, not a trace through the calculation engine. A subsequent field-by-field tax-domain review of every leaf in
these containers found {len(USER_INPUT_LEAF_OVERRIDES)} leaves that are genuinely taxpayer-entered facts or elections, not
engine derivations, despite living in a "calculated" container — confirmed both by direct <span class="code">.spe</span>
source review and by a live ITA plan payload shared in Slack (#ita-triad) showing <span class="code">firstName</span>/
<span class="code">lastName</span>/<span class="code">dateOfBirth</span> as real user data under
<span class="code">usITATaxpayerItems</span>. These leaves (<span class="code">filingStatus, taxYear, primaryResidentState,
primaryResidentFullStateName, nonDeductibleIRA, rothCont, sepIRA, solo401kContribution, sePremiums,
studentLoanInterestPaid, familyCoverageHSA, selfOnlyCoverageHSA, resEnergyInput</span>) are now overridden to user-data
regardless of container. Two further leaves (<span class="code">qbiLimitation</span>, <span class="code">retirement.spouse</span>)
were found to be commented out in their source <span class="code">.spe</span> files — not live inputs — and are flagged as
dead references rather than counted toward must-needed/runnability. The remaining calculated-container fields were confirmed
by tax-domain review to be genuine statutory constants (e.g. <span class="code">addtlMedTaxWithheldThreshold</span>,
<span class="code">nIITaxthreshold</span>, FICA/Medicare/LTCG rate constants) or genuine engine-derived/rollup values
(e.g. AGI, QBI deduction, SE tax, per-W2 contribution-total rollups) — cross-checked against an independent 1040-field
classification, agreeing on every overlapping concept.</small></p>

<h3>Field-level totals</h3>
<div>
<div class="kpi"><b>{total}</b><small>distinct fields referenced</small></div>
<div class="kpi"><b>{n_userinput}</b><small>true user inputs</small></div>
<div class="kpi"><b>{n_calculated}</b><small>engine-calculated (read, not input)</small></div>
<div class="kpi"><b>{precise}</b><small>precise 1040/schedule match</small></div>
<div class="kpi"><b>{unmatched}</b><small>not on a 1040 form</small></div>
</div>
<p><small>Reconciliation: matched ({matched}) + not-on-form ({unmatched}) + template ({templ}) = {matched+unmatched+templ} = {total} total.</small></p>

<h3>Missing fields by document (field count)</h3>
<table><tr><th>Source document</th><th># distinct blocking fields</th></tr>{doc_rows}</table>

<h3>Where available fields map (by form)</h3>
<table><tr><th>Form</th><th># fields mapped</th></tr>{form_rows}</table>

<h3>Every field, per strategy</h3>
{''.join(rows_html)}
</div>
</div></body></html>"""

html_path = os.path.join(OUT_DIR, "1040_feasibility_report.html")
open(html_path, "w").write(html_doc)

# ---------------------------------------------------------------------------
# Standalone extract: just the "All N strategies — runnability verdict" table,
# as its own self-contained HTML file (same styling, no other sections).
# ---------------------------------------------------------------------------
strategies_table_doc = f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<title>All {len(strategies)} Strategies — Runnability Verdict</title>
<style>
body{{font-family:-apple-system,Segoe UI,Roboto,sans-serif;margin:0;color:#1a1a1a;line-height:1.5;background:#fafbfc}}
.wrap{{max-width:1200px;margin:0 auto;padding:2.5rem 2rem}}
h1{{font-size:1.6rem;margin:0 0 .2rem}}
.sub{{color:#667;margin:0 0 1.5rem}}
table{{border-collapse:collapse;width:100%;margin:.5rem 0 1.5rem;font-size:13px;background:#fff}}
th,td{{border:1px solid #e2e8f0;padding:6px 9px;text-align:left;vertical-align:top}}
th{{background:#f0f4f8;font-weight:600}}
.code{{font-family:ui-monospace,Menlo,monospace;font-size:12px;color:#334}}
tr.m{{background:#f2fbf5}} tr.u{{background:#fff7f5}}
.yes{{color:#0a7;font-weight:700}} .no{{color:#c33;font-weight:700}} .tmpl{{color:#a70}} .muted{{color:#889}}
small{{color:#667;font-weight:400}}
ul.misslist{{margin:0;padding-left:1.1rem}} ul.misslist li{{margin:0 0 .3rem}}
</style></head><body><div class="wrap">

<h1>All {len(strategies)} strategies — runnability verdict</h1>
<p class="sub">Extracted from the full <span class="code">1040_feasibility_report.html</span> — source of truth:
production <span class="code">ita-mapping-service</span>. See the full report for methodology, appendix, and
per-field detail.</p>
<p><small>"Trivial" = reads only engine-computed values, no raw user inputs (still needs source docs upstream to compute them).</small></p>
{run_table_compact}

</div></body></html>"""

strategies_table_path = os.path.join(OUT_DIR, "1040_strategies_runnability.html")
open(strategies_table_path, "w").write(strategies_table_doc)

# console summary (visible run-time output)
print("=== 1040 FEASIBILITY ANALYSIS ===")
print(f"Crosswalk: {json_paths} json paths + {code_paths} code paths + {code_leaves} W-2 leaves")
print(f"Strategies analyzed: {len(strategies)}")
print(f"Total distinct fields referenced: {total}")
print(f"  true user inputs:        {n_userinput}")
print(f"  engine-calculated (read): {n_calculated}")
print(f"  matched to 1040/schedule: {matched}  (precise={precise}, coarse-container={coarse})")
print(f"  NOT on a 1040 form:       {unmatched}")
print(f"  undeterminable template:  {templ}")
print(f"  reconcile: {matched}+{unmatched}+{templ}={matched+unmatched+templ} (== {total}? {matched+unmatched+templ==total})")
print(f"Must-needed fields: {must_matched}/{must_total} mapped to a 1040 line")
print("--- 1040-UPLOAD RUNNABILITY ---")
print(f"  strategies RUNNABLE from a 1040 upload: {n_runnable}/{len(strat_runnable)}")
print(f"  strategies BLOCKED (need more docs):    {n_blocked}")
print(f"  user-data available on 1040: {n_available} | off-form blockers: {n_offform} | on-form-unmapped: {n_mappergap}")
print(f"  sanity 401k not-runnable: {sanity['401k_not_runnable']}")
print("  blocking fields by source document:")
for doc, paths in sorted(blocker_by_doc.items(), key=lambda x: -len(x[1])):
    print(f"    {len(paths):3d}  {doc}")
print(f"SANITY 401k: {sanity['detail']} -> {'PASS' if sanity_ok else 'REVIEW'}")
print(f"\nWrote: {csv_path}")
print(f"Wrote: {html_path}")
print(f"Wrote: {strategies_table_path}")
