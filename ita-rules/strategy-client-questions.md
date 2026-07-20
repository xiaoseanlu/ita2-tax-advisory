# Master qualifying questions (three-line extract)

For each strategy, up to **three** lines were taken **verbatim** from the folder `QUALIFYING_QUESTIONS.md` that contains that strategy (`entity/`, `individual/`, `business/`, `retirement/`, `credits/`, or `charitable/`). Under each strategy heading they appear in a fixed order: first a structural or eligibility-framing line, then the first primarily numeric-threshold line from the source list (when one was chosen), then a blocking or exclusionary line (when one was chosen).

If no numbered question in that strategy clearly fit a slot, that slot is omitted (no paraphrase and no filler text). **ita_032** and **ita_038** do not appear in those files. **ita_037** has only two source questions in the folder file; both are included here verbatim.

Screening only—not tax advice.

---

## `ita_001` — Real Estate Professional Status Election

3. Are the activities within the statutory list (development, rental, management, brokerage, etc.) rather than only **investor-type** work (e.g., reviewing financials, arranging financing) that may **not** count?

1. Does the taxpayer (or spouse, on a joint return) perform **more than 50%** of all **personal services** for the year in **real property trades or businesses**?

6. Is the taxpayer **not** a W-2 employee in a real property business unless they own **≥5%** of that employer?

---

## `ita_002` — S Corporation Choice of Entity Election  
1. Is the entity **domestic** and eligible to elect **S** status (corporation or LLC taxed as corporation)?

2. Will shareholder count stay **≤100** and are all shareholders **allowed types** (individuals, certain trusts, estates)?

4. Are **all** shareholders **U.S. citizens or residents** (no ineligible foreign owners)?

---

## `ita_003` — S Corporation Reasonable Compensation Analysis and Optimization  
1. Does the shareholder **actually perform services** for the corporation?

6. For **2026**, has modeling used the **Social Security wage base $184,500** (and Medicare rules) instead of older figures in the JSON?

4. Is compensation **not de minimis** if the shareholder provides substantial services (avoid **zero salary** patterns)?

---

## `ita_004` — Pass-Through Entity Selection and Optimization  
1. Has the taxpayer compared **liability**, **operational flexibility**, and **administrative cost** across sole prop / partnership / LLC / S corp?

3. Has **§199A QBI** been modeled for each structure, including **2026** threshold / phase-in amounts (**MFJ** roughly **$403,500–$553,500** wage/SSTB band per **Rev. Proc. 2025-32**)?

---

## `ita_005` — HSA and Health Care FSA Coordination  

1. Is the taxpayer enrolled in a **qualifying HDHP** without disqualifying non-HDHP coverage (including a spouse’s plan covering them)?

4. Will contributions respect **2026 HSA limits** ($4,400 / $8,750 + $1,000 catch-up)?

5. Is the taxpayer **not** on **Medicare** and **not** a tax **dependent**?

---

## `ita_006` — Employee Accountable Reimbursement Plan  

1. Do claimed expenses have a clear **business connection** to the employee’s services?

2. Is there **adequate accounting** (amount, time, place, business purpose, relationship) within a **reasonable period** (JSON cites ~**60 days** substantiation / **120 days** return of excess)?

4. Are **personal** costs excluded (including mixed-use items allocated)?

---

## `ita_007` — Employer Accountable Plan Design & Administration  

1. Is there a **written** accountable plan before reimbursements flow?

4. For **mileage**, is reimbursement **≤ IRS business standard mileage rate** (**72.5¢/mile for 2026**) unless actual-cost method is used?

2. Are **ineligible** employer deductions (fines, political, personal) blocked from reimbursement?

---

## `ita_008` — Bunching Itemized Deductions Strategy  

1. Are **itemized** deductions naturally near the **2026 standard deduction** so alternating years produces a net benefit?

2. Has the taxpayer modeled **2026 federal SALT rules** (OBBBA increased caps for many filers through **2029**—do not assume a **$10,000** cap without current-year confirmation)?

---

## `ita_009` — Business Use of Home  

1. Is the workspace **exclusive** and **regular** for business?

4. Will they choose **simplified** ($5/ft², max **$1,500**) vs **actual** method consistently?

3. For **employees**, does the home office satisfy **employer’s convenience** tests—and has the taxpayer verified **2026 law** on employee deductions (JSON references TCJA suspension through **2025**)?

---

## `ita_010` — Combined Business & Personal Travel  

1. Is the **primary purpose** of the trip **business** (domestic transportation rule)?

4. Are **50% meal** rules and any **per diem** elections applied correctly?

5. Are **cruise / investment seminar / lavish** disallowance rules screened?

---

## `ita_011` — Employer Student Loan Repayment Assistance (§127)  

1. Does the employer maintain a **written §127 educational assistance program**?

3. Will total **§127** benefits (tuition + loans) stay within the **$5,250** annual cap (indexed **after 2026** per OBBBA summaries—confirm for late-2026 plan years)?

4. Are payments for the **employee’s own** qualifying loans (not relatives’) with documentation?

---

## `ita_012` — Dependent Care FSA  

1. Does the employer offer a **§125 dependent care FSA**?

4. Will elections stay within **$5,000** household cap (**$2,500 MFS**)?

5. Is the provider **not** a excluded relationship (spouse, tax dependent, child **<19**, etc.)?

---

## `ita_013` — Health Care FSA Optimization  

1. Does the employer offer a **§125 health FSA**?

2. Will the election stay within **$3,400** (2026 IRS cap) unless the employer sets a lower limit?

4. Is the taxpayer **not** concurrently making **HSA contributions** unless the FSA is **limited-purpose**?

---

## `ita_014` — Pre-Tax Health Insurance Premium Deduction  

1. **Employees:** are premiums run through a **§125** plan (pre-tax wages)?

6. For **LTC premiums**, has the taxpayer applied **2026** age-based caps (see annual IRS/medical limits table)?

3. Is the taxpayer **ineligible** for subsidized **employer** coverage (including spouse’s plan) for the months claimed?

---

## `ita_015` — HSA Maximization  

1. Is the taxpayer HDHP-eligible all year (or using proration / **last-month** rule consciously)?

2. Will contributions target **2026 limits** ($4,400 / $8,750 + $1,000 catch-up)?

3. Is there **no disqualifying coverage** (Medicare, impermissible FSA, spouse non-HDHP that covers them)?

---

## `ita_016` — MERP (§105) for Small Business  

1. Is there a **written §105** plan and employer-only funding (no salary reduction)?

3. If **S corp 2%+**, does the JSON exclusion apply (typically **cannot participate** in MERP as described)?

4. Are **sole props/partners** excluded from **employee-only** MERP benefits as owners (per JSON)?

---

## `ita_017` — Like-Kind Exchange (§1031) Real Property  

1. Are both properties **U.S. real property** held for **investment or business**?

3. Can identification meet the **45-day** rule and closing the **180-day** rule?

5. Are **dealer / inventory / primary residence** exclusions confirmed?

---

## `ita_018` — Augusta Rule (§280A) ≤14 Days  

5. Is the property a **dwelling unit** used as a residence?

1. Is total rental **≤14 days** (or the JSON’s alternate **10%-of-rented-days** test if applicable)?

4. Does the taxpayer accept **no rental-expense deductions** for those days?

---

## `ita_019` — Capital Gain Timing and Recognition Planning  

1. Are positions past the **>12-month** holding period where long-term rates are desired?

2. Has the taxpayer modeled **2026 ordinary taxable income brackets** (MFJ **12%→22%** breakpoint **$100,800** taxable ordinary income on IRS **2026** tables) when stacking **0% LTCG**?

---

## `ita_020` — Hiring Children in Family Business  

1. Is the work **real**, age-appropriate, and **documented** (time, tasks, pay)?

5. For **2026**, is the child’s standard deduction modeled using **current-year** amounts (e.g., **$16,100** single OBBBA standard deduction on IRS tables—confirm annually)?

3. For **FICA/FUTA** exemptions in the JSON, is the entity form **sole prop / partnership with only parents** (not **S or C corp**)?

---

## `ita_021` — Hiring Spouse in Family Business  

1. Is there a true **employer–employee** relationship (not co-owner treatment)?

4. Are **S corp 2%** fringe rules considered if applicable?

---

## `ita_022` — Tax Loss Harvesting — Long-Term Capital Losses  

1. Are lots identified with **>12 months** holding period and **basis** documentation?

2. Will replacement avoid **substantially identical** securities for **61 days**?

---

## `ita_023` — Tax Loss Harvesting — Short-Term Capital Losses  

1. Are positions **≤12 months** if short-term character is required?

2. Is **trade date** (not settlement) used for the holding period?

4. Are **wash sale** and **related party** rules satisfied?

---

## `ita_024` — Installment Sale Gain Deferral  

1. Will at least one payment be received **after** the year of sale?

3. Is **imputed interest** at least **AFR**?

5. Is property **ineligible** type (publicly traded stock, dealer property, etc.) ruled out?

---

## `ita_025` — Bonus Depreciation (incl. 6,000+ lb vehicles)  

1. Is MACRS class life **≤20 years** (or otherwise qualifying property, including **QIP** where eligible)?

3. Is **business use >50%** documentable (listed property rules)?

2. Does **original use** or **used-property acquisition** test pass?

---

## `ita_026` — Section 179 Election  

1. Is property **§179-eligible** (tangible personal property, listed categories of real property improvements, etc.)?

3. For **TY2026**, is total §179 property below the **$4,090,000** investment phase-out threshold (with **$2,560,000** max deduction and **$32,000** heavy SUV limit per **Rev. Proc. 2025-32**)?

4. Is the taxpayer limited by **§179(b)(3) aggregate active trade or business taxable income** (cannot invent losses)?

---

## `ita_027` — Cost Segregation Study  

2. Is a **qualified** study provider used (engineering support for audit)?

1. Is building cost high enough (JSON suggests **~$500k+**) for ROI vs study fee?

4. Is there **taxable income** to absorb accelerated deductions?

---

## `ita_028` — QBI (§199A)  

1. Is income from a **qualified trade or business** (Schedule C, K-1, eligible rental as T/B)?

2. For **TY2026**, is **taxable income** modeled against **MFJ** threshold **$403,500** and **§199A(b)(3)** phase-in completion **$553,500** (other filing statuses use **Rev. Proc. 2025-32** table)?

---

## `ita_029` — QBI Phase-Out / Limitation Planning  

2. For **non-SSTB**, can **W-2** or **qualified property** be increased **legitimately**?

1. Is **taxable income** near the **2026** band (**$403,500–$553,500 MFJ** per **Rev. Proc. 2025-32**) where wages/UBIA/SSTB rules bite?

3. For **SSTB**, is planning focused on **income** relative to the same **2026** thresholds?

---

## `ita_030` — Startup Cost Amortization Election  

1. Were costs incurred **before** the business began?

3. Is the **$5,000** immediate + **$50,000 / $55,000** phase-out grid applied to total costs?

2. Do costs qualify as **investigatory / startup** vs nondeductible acquisition costs?

---

## `ita_031` — Startup Expense Immediate Deduction Strategy  

1. Same startup vs organizational split as **`ita_030`**—are both **$5,000** buckets maximized where allowed?

2. Is total spend managed vs the **$50k/$55k** phase-out grid?

---

## `ita_033` — 401(k) with Age 60+ / Catch-Up Optimization  

1. Is the employee eligible to defer under the plan (entry dates, union exclusions, etc.)?

2. Will **2026** elective deferrals respect **$24,500** base (and **$32,500** with regular **$8,000** catch-up for age **50+**)?

4. Does **ADP/ACP** testing or **HCE** status cap deferrals below the statutory max?

---

## `ita_034` — 401(k) Employee Salary Deferrals  

1. Same eligibility and **$24,500 / +$8,000** catch-up **2026** limits as above?

2. Is the taxpayer **highly compensated** (often prior-year compensation **>$160,000** for **2026 HCE** classification—confirm with employer)?

---

## `ita_035` — 401(k) Employer Match Maximization  

1. Does the SPD define the **match formula** and **compensation** definition (bonus included?)?

4. Do **$72,000** §415(c) totals cap combined deferrals, match, and after-tax additions?

---

## `ita_036` — 403(b) Employee Deferrals  

1. Is employer type eligible (**public school**, **501(c)(3)**, church plan)?

2. Will **2026** deferrals use the same **$24,500 / +$8,000** limits as 401(k)?

3. If claiming the **15-year catch-up**, does the plan satisfy service rules—and has the taxpayer confirmed against **2026** plan text and current law whether it can stack with the **age 50+** catch-up (the JSON states they **cannot** be used together)?

---

## `ita_037` — 403(b) Employer Match  

1. Same match, vesting, true-up, and **$72,000** cap questions as **`ita_035`**, but read against the **403(b) SPD**?

2. Is **457(b)** stacking still relevant?

---

## `ita_039` — Backdoor Roth IRA  

1. Is **MAGI** above **2026 Roth contribution** phase-outs (**~$242,000–$252,000 MFJ**; **~$153,000–$168,000** single/HoH—confirm Form 8606 instructions)?

2. Is there **earned income** at least equal to the contribution?

4. Will **pre-tax IRA/SEP/SIMPLE** balances be rolled into **401(k)** to avoid the **pro-rata** rule?

---

## `ita_040` — Mega Backdoor Roth (After-Tax 401(k))  

1. Does the plan allow **after-tax** employee contributions?

3. Are **2026** limits modeled: **$72,000** §415(c) **minus** elective deferrals **minus** employer contributions **=** after-tax room?

5. Are **ACP** testing and **HCE** limits evaluated?

---

## `ita_041` — Direct Roth IRA Contribution  

1. Is **MAGI** **below** the **2026** phase-out range for the filing status?

2. Is earned income at least the contribution (capped at **$7,500**, or **$8,500** at age **50+** for **2026** per IRS IRA announcements)?

3. Is the combined **traditional + Roth IRA** limit respected?

---

## `ita_042` — Roth IRA Conversion  

1. Is there pre-tax IRA/SEP/SIMPLE balance to convert?

3. For **SIMPLE**, has the **2-year** rule from first contribution been satisfied?

4. Will **RMDs** be taken **before** converting remaining balance?

---

## `ita_043` — SEP-IRA  

1. Is the sponsor a **self-employed** or small-business employer eligible for SEP?

2. For **2026**, is the contribution capped at the lesser of **$72,000** or **25% of compensation** (20% of net earnings from self-employment after SE tax deduction for self-employed)?

4. Is the taxpayer aware there is **no** **$8,000** catch-up in SEP (only IRAs/401k-style plans)?

---

## `ita_044` — Solo 401(k) Maximization  

1. Is there **no** eligible employee other than owner (**and spouse** if permitted)?

2. Are **2026** limits modeled: **$24,500** deferral + **$8,000** catch-up if **50+**, plus employer profit sharing up to **§415(c) $72,000** total?

4. Is **Form 5500-EZ** required if assets **>$250,000**?

---

## `ita_045` — Traditional IRA Deductible Contributions  

1. Is there **earned income** at least equal to the contribution?

2. For **2026**, is the contribution limit **$7,500** (**$8,500** age **50+**) combined across **traditional + Roth**?

3. If **covered** by a workplace plan, does **MAGI** fall outside the **2026** deduction phase-outs (typical published ranges: **single $81,000–$91,000**; **MFJ covered spouse $129,000–$149,000**; **MFJ uncovered taxpayer with covered spouse $242,000–$252,000**—confirm IRS tables)?

---

## `ita_046` — Research and Development (R&D) Tax Credit  

1. Does the work meet the **four-part test** (permitted purpose, uncertainty, process of experimentation, technological in nature)?

5. For a **payroll-tax offset**, does average gross receipts and startup age meet the small-business tests in current law (JSON cites **<$5M** receipts and **first 5 years**—confirm for the filing year)?

3. Is the activity **not** primarily social sciences / humanities / market research excluded as non-qualifying?

---

## `ita_047` — Child Tax Credit Optimization  

1. Is there a **qualifying child under age 17** at year-end who meets relationship, residency, support, joint-return, and dependent tests?

3. For **2026**, is the credit modeled at **$2,200 per qualifying child** under **OBBBA** (replacing older **$2,000** figures in the JSON)?

7. If **married filing separately**, does an exception apply (generally credit is limited or unavailable)?

---

## `ita_048` — Residential Energy Efficient Property Credits  

1. Is the property the taxpayer’s **principal residence** in the **United States**?

4. Does the taxpayer understand **§25C annual caps** in the JSON (**$1,200** general bucket, **$2,000** heat-pump bucket, **$3,200** combined)?

9. Is the install **rental or pure business** use excluded from these **residential** credits (different rules may apply)?

---

## `ita_049` — Charitable Donation of Appreciated Securities  

1. Does the taxpayer own **publicly traded or other securities** they are willing to give to charity (not sell for cash first)?

2. Has the property been held **more than 12 months** (long-term) before donation?

3. Is the intended donee a **qualified 501(c)(3) public charity** (and, per the strategy file, **not** a donor-advised fund if relying on **full FMV** deduction treatment as described in criteria)?

---

## `ita_050` — Donor-Advised Fund (DAF) Strategic Contributions  

2. Is the taxpayer willing to contribute only to a **DAF sponsored by a public charity** (cash, appreciated securities, or other assets per the file)?

9. For **cash** contributions, is the donor within the file’s **60% of AGI** limit; for **appreciated securities**, within **30% of AGI**, with **5-year carryforward** for excess?

3. Does the taxpayer accept that contributed amounts are **irrevocable** and **cannot be reclaimed** for personal use?

---

## `ita_051` — IRA Qualified Charitable Distribution (QCD)  

2. Will the transfer be made **directly from the IRA trustee** to a **qualified 501(c)(3) public charity** (not to the taxpayer first)?

1. Was the taxpayer **age 70½ or older** on the date of the distribution (file stresses **date-based** rule, not merely turning 70 in-year)?

5. Will the donee **not** be a **private foundation**, **donor-advised fund**, or **supporting organization** (per restrictions)?

---

*End of master extract.*
