def calculate_comprehensive_deduction(year, status, magi, 
                                      filer_65=False, filer_blind=False, 
                                      spouse_65=False, spouse_blind=False):
    """
    Final logic accounting for:
    1. Base Standard Deduction (Yearly adjustment)
    2. Additional Standard Deduction (Age/Blindness - No phase-out)
    3. OBBBA Senior Bonus (2025+ - Phase-out applies)
    """
    data = {
        2024: {"MFJ": 29200, "QSS": 29200, "HOH": 21900, "Single": 14600, "MFS": 14600, "extra_m": 1550, "extra_s": 1950},
        2025: {"MFJ": 31500, "QSS": 31500, "HOH": 23625, "Single": 15750, "MFS": 15750, "extra_m": 1600, "extra_s": 2000},
        2026: {"MFJ": 32200, "QSS": 32200, "HOH": 24150, "Single": 16100, "MFS": 16100, "extra_m": 1650, "extra_s": 2050}
    }
    _key = {"MFJ": "MFJ", "QSS": "QSS", "MFS": "MFS", "HOH": "HOH", "SINGLE": "Single"}

    s = status.upper()
    key = _key.get(s, s)
    is_married_type = key in ["MFJ", "QSS", "MFS"]
    base = data[year][key]
    
    # 1. Traditional Additional Deduction (Age + Blindness)
    # This is a per-condition, per-person check. 
    # A single person who is 65 AND blind gets TWO 'extra' amounts.
    rate = data[year]["extra_m"] if is_married_type else data[year]["extra_s"]
    
    conditions = 0
    if filer_65: conditions += 1
    if filer_blind: conditions += 1
    if is_married_type: # Spouse only counts if filing jointly or QSS
        if spouse_65: conditions += 1
        if spouse_blind: conditions += 1
        
    additional_std = conditions * rate
    
    # 2. OBBBA Senior Bonus ($6,000 per person age 65+)
    # Note: Blindness does NOT increase the Senior Bonus; it only affects Layer 1.
    bonus = 0
    if year >= 2025:
        num_seniors = (1 if filer_65 else 0) + (1 if spouse_65 else 0)
        max_bonus = num_seniors * 6000
        threshold = 150000 if key in ["MFJ", "QSS"] else 75000
        
        if magi > threshold:
            reduction = (magi - threshold) * 0.06
            bonus = max(0, max_bonus - reduction)
        else:
            bonus = max_bonus

    return {
        "Year": year,
        "Base": base,
        "Age/Blindness Add-on": additional_std,
        "Senior Bonus": round(bonus, 2),
        "Total Deduction": round(base + additional_std + bonus, 2)
    }