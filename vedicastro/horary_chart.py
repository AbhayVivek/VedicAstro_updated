import os
import polars as pl
import swisseph as swe
from typing import Tuple
from datetime import datetime
from .utils import dms_to_decdeg, utc_offset_str_to_float

## Global Constants
SWE_AYANAMAS = { "Krishnamurti" : swe.SIDM_KRISHNAMURTI, "Krishnamurti_New": swe.SIDM_KRISHNAMURTI_VP291,
                "Lahiri_1940": swe.SIDM_LAHIRI_1940, "Lahiri_VP285" : swe.SIDM_LAHIRI_VP285, "Lahiri_ICRC" : swe.SIDM_LAHIRI_ICRC,
                "Raman" : swe.SIDM_RAMAN, "Yukteshwar" : swe.SIDM_YUKTESHWAR}

# Determine the absolute path to the directory where this script is located
current_dir = os.path.abspath(os.path.dirname(__file__))
csv_file_path = os.path.join(current_dir, "data", "KP_SL_Divisions.csv")
## Read KP SubLord Divisions CSV File
KP_SL_DMS_DATA = pl.read_csv(csv_file_path)
KP_SL_DMS_DATA = KP_SL_DMS_DATA\
                .with_columns(pl.arange(1, KP_SL_DMS_DATA.height + 1).alias("SL_Div_Nr"))\
                .with_columns([
                    pl.col('From_DMS').map_elements(dms_to_decdeg).alias('From_DecDeg'),
                    pl.col('To_DMS').map_elements(dms_to_decdeg).alias('To_DecDeg'),
                    pl.col("From_DMS").str.replace_all(":", "").cast(pl.Int32).alias("From_DMS_int"),
                    pl.col("To_DMS").str.replace_all(":", "").cast(pl.Int32).alias("To_DMS_int")
                ])

def jd_to_datetime(jdt: float, tz_offset: float):
    utc = swe.jdut1_to_utc(jdt) 
    # Convert UTC to local time - note negative sign before tzoffset to convert from UTC to IST
    year, month, day, hour, minute, seconds  = swe.utc_time_zone(*utc, offset = -tz_offset)
    # Convert the fractional seconds to microseconds
    microseconds = int(seconds % 1 * 1_000_000)
    return datetime(year, month, day, hour, minute, int(seconds), microseconds)

def get_horary_ascendant_degree(horary_number: int):
    """
    Convert a horary number to ascendant degree of the starting subdivision
    """
    if 1 <= horary_number <= 249:
        row = KP_SL_DMS_DATA.filter(pl.col("SL_Div_Nr") == horary_number).select(["Sign", "From_DMS", "From_DecDeg"])
        data = row.to_dicts()[0]

        # Convert the sign to its starting degree in the zodiac circle
        sign_order = {'Aries': 0, 'Taurus': 30, 'Gemini': 60, 'Cancer': 90,
                    'Leo': 120, 'Virgo': 150, 'Libra': 180, 'Scorpio': 210,
                    'Sagittarius': 240, 'Capricorn': 270, 'Aquarius': 300, 'Pisces': 330 
                    }
        
        sign_start_degree = sign_order[data['Sign']]

        # Convert From_DecDeg to zodiac degree location
        zodiac_degree_location = sign_start_degree + data['From_DecDeg']
        data['ZodiacDegreeLocation'] = zodiac_degree_location
        return data
    else:
        return "SL Div Nr. out of range. Please provide a number between 1 and 249."


def find_exact_ascendant_time(year: int, month: int, day: int, utc_offset: float, lat: float, lon: float, horary_asc_deg: float, ayanamsa : str) -> datetime:
    """
    Finds the exact time when the Ascendant is at the desired degree.

    Parameters:
    - year: year of the horary question (prasna)
    - month: month of the horary question
    - day: day of the horary question
    - utc_offset: The UTC offset of the horary question's location, i.e of the predictor (astrologer)
    - lat: Latitude pertaining to the horary question's predictor (astrologer)
    - lon: Longitude pertaining to the horary question's predictor (astrologer).
    - horary_asc_deg: The desired Ascendant degree on the zodiac to match.
    - ayanamsa: The ayanamsa to be used when constructing the chart

    Returns:
    - matched_time: a datetime object, when the Ascendant matches the desired degree.
    If no match is found within the day, returns None.
    """
    swe.set_sid_mode(SWE_AYANAMAS.get(ayanamsa))  # set the ayanamsa
    utc = swe.utc_time_zone(year, month, day, hour = 0, minutes = 0, seconds = 0, offset = utc_offset)
    jd_start,_ = swe.utc_to_jd(*utc) ## Unpacks utc tuple
    jd_end = jd_start + 1  # end of the day

    current_time = jd_start
    while current_time <= jd_end:
        current_time_dt = jd_to_datetime(current_time, utc_offset)
        cusps, _ = swe.houses_ex(current_time, lat, lon, b'P', flags = swe.FLG_SIDEREAL)
        asc_lon_deg = cusps[0]
        if abs(asc_lon_deg - horary_asc_deg) < 0.0001: # and (asc_lon_deg > horary_asc_deg):
            print(f"Matched Time: {current_time_dt} || Final Ascendant: {asc_lon_deg}")
            return jd_to_datetime(current_time, utc_offset)
        current_time += 1.0 / (24 * 60 * 60 * 10)  # increment by 1 deci-second

    print("No matching Ascendant time found for the given input")
    return None


if __name__== "__main__":
    year = 2024
    month = 2
    day = 5
    hour = 9
    minute = 5
    secs = 0
    horary_number = 34
    latitude, longitude, utc = 11.020085773931049, 76.98319647719487, "+5:30" ## Coimbatore
    ayan = "Krishnamurti"

    horary_asc = get_horary_ascendant_degree(horary_number)
    desired_asc = horary_asc["ZodiacDegreeLocation"]
    print(f'Desired Asc Lon: {desired_asc} °')
    matched_time = find_exact_ascendant_time(year, month, day, utc_offset_str_to_float(utc), latitude, longitude, desired_asc, ayan)