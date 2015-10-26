from django.http import HttpResponse
import json
import requests
import urllib
import time
import math
import itertools
from models import CROP_NAME
from collections import defaultdict
from models import CropPrice
from django.utils.functional import lazy, memoize

import parse_nass

def fcRequest(req):
  def waitForData(result):
    if result.startswith('"completed'):
      return result
    else:
      try:
        hash = result[result.index("hash=") + 5:]
      except ValueError:
        print "Oops: result: \n", result
        return

      while True:
        result = requests.get("http://fetchclimate2-dev.cloudapp.net/api/status?hash=" + hash).text
        if result.startswith('"completed'):
          return result
        time.sleep(4)

  def getData(query):
    blob = query[query.index("Blob=") + 5: -1]
    result = requests.get("http://fetchclimate2-dev.cloudapp.net/jsproxy/data?uri=" + urllib.quote_plus(
      "msds:ab?AccountName=fc2cache&Container=requests&Blob=" + blob) + "&variables=lat,lon,values").text
    return result

  def compute():
    r = requests.post("http://fetchclimate2-dev.cloudapp.net/api/compute", json=req,
                      headers={'content-type': 'application/json'})
    return r.text

  query = compute()
  query = waitForData(query)
  return getData(query)

def toRadians(degrees):
  return float(degrees) / 180 * math.pi
def toDegrees(radians):
  return float(radians) / math.pi * 180 

EARTH_RADIUS = 6371009.0

# Note, we don't handle discontinuities at the moment
def circle_lat_lon_radii(lat, radius):
  # returns the latitude and longitude radii for a circle at the given latitude and radius in meters
  lat_delta = toDegrees(float(radius) / EARTH_RADIUS)
  lon_delta = toDegrees(float(radius) / EARTH_RADIUS / math.cos(toRadians(lat)))
  return (lat_delta, lon_delta)

def distance(lat1, lon1, lat2, lon2):
  # Only accurate for short distances (less than a hundred miles or so) not near the poles.
  average_phi = (toRadians(lat1) + toRadians(lat2)) / 2.0
  phi_delta = toRadians(lat2) - toRadians(lat1)
  lambda_delta = toRadians(lon2) - toRadians(lon1)
  return EARTH_RADIUS * math.sqrt(phi_delta ** 2 + (lambda_delta * math.cos(average_phi)) ** 2)

CROP_YEARS = range(2010, 2015)

def cropscape_json(lat, lon, radius):
  (lat_delta, lon_delta) = circle_lat_lon_radii(lat, radius)
  lats = [lat - lat_delta + (lat_delta / 10) * i for i in xrange(21)]
  lons = [lon - lon_delta + (lon_delta / 10) * i for i in xrange(21)]

  json = {
    "EnvironmentVariableName": "CropScape",
    "Domain": {
      "Mask": None,
      "SpatialRegionType": "CellGrid",
      "Lats": lats,
      "Lons": lons,
      "Lats2": None,
      "Lons2": None,
      "TimeRegion": {
        "Years": CROP_YEARS,
        "Days": [1, 366],
        "Hours": [0, 24],
        "IsIntervalsGridYears": False,
        "IsIntervalsGridDays": True,
        "IsIntervalsGridHours": True
      }
    },
    "ParticularDataSources": {},
    "ReproducibilityTimestamp": int(time.time() * 1000)
  }
  return json

def divider_midpoints(dividers):
  # Returns the midpoints of each grid cell range
  return [(x1 + x2) / 2 for (x1, x2) in zip(dividers[:-1], dividers[1:])]

def crop_name(index):
  return CROP_NAME[index]

def commodity_name(crop_name):
  upper_name = crop_name.upper()
  if upper_name.startswith("DOUBLE CROP"):
    crops = upper_name.split(" - ")[1].split("/")
    commodities = []
    for c in crops:
      commodities += commodity_name(c)
    return commodities
  if upper_name.endswith("WHEAT"):
    wheat_variety = upper_name.split()[0]
    if wheat_variety == "DURUM":
      wheat_variety = "SPRING, DURUM"
    return [("WHEAT", wheat_variety)]
  elif crop_name == "Dry Beans":
    return [("BEANS", "DRY EDIBLE")]
  elif crop_name == "Other Hay (non-alfalfa)":
    return [("HAY", "(EXCL ALFALFA)")]
  elif upper_name == "ALFALFA":
    return [("HAY", "ALFALFA")]
  elif crop_name == "Honeydew Melons":
    return [("MELONS", "HONEYDEW")]
  elif crop_name == "Watermelons":
    return [("MELONS", "WATERMELON")]
  else:
    return [(upper_name, None)]

def make_top_crop_chart_data(crops):
  top_crop_chart_data_points = []
  for crop in crops:
    top_crop_chart_data_points.append({
      "x": crop["shortName"],
      "y": [crop["pctAcres"]],
      "tooltip": "%0.1f%%" % (crop["pctAcres"] * 100.0)
    })
  return {
    "series": ["% Acres"],
    "data": top_crop_chart_data_points
  }

def make_acre_change_chart(crop_data):
  data_points = []
  for year, pct_acres in zip(CROP_YEARS, crop_data["history"]):
    data_points.append({
      "x": int(year),
      "y": [pct_acres],
      "tooltip": "%s: %0.1f%%" % (year, pct_acres * 100.0)
    })
  change = "rose" if crop_data["pctAcresDelta"] > 0 else "fell"
  title = "%s: acreage %s %0.0f%%" % (crop_data["name"], change, abs(crop_data["pctAcresDelta"] * 100.0))
  return {
    "title": title,
    "series": ["% Acres"],
    "data": data_points
  }

def make_price_change_chart(price_data, min_year):
  data_points = []
  years = price_data["annualPrices"].keys()
  # Produce a value for every year, inserting a 0 if no data for a year.
  for year in xrange(max(min_year, min(years)), max(years) + 1):
    try:
      price = price_data["annualPrices"][year]
    except KeyError:
      price = 0
      price_string = "No data"
    else:
      price_string = "$" + make_price_string(price)
    tooltip = "%s: %s" % (year, price_string)
    data_points.append({
      "x": int(year),
      "y": [float(price)],
      "tooltip": tooltip
    })
  change = "rose" if price_data["priceDeltaPct"] > 0 else "fell"
  # strip leading sign from the pctAcresDelta value
  title = "%s: prices %s %0.0f%%" % (price_data["crop"], change, abs(price_data["priceDeltaPct"] * 100.0))
  return {
    "title": title,
    "series": ["$ / %s" % price_data["unit"]],
    "data": data_points
  }


def roundrobin(*iterables):
  "roundrobin('ABC', 'D', 'EF') --> A D E B F C"
  # Recipe credited to George Sakkis
  pending = len(iterables)
  nexts = itertools.cycle(iter(it).next for it in iterables)
  while pending:
    try:
      for next in nexts:
        yield next()
    except StopIteration:
      pending -= 1
      nexts = itertools.cycle(itertools.islice(nexts, pending))

def make_top_trends_chart_data(crops):
  # Find the top two greatest acre changes and price changes.
  topAcreChanges = sorted(crops, key=lambda x: -abs(x["pctAcresDelta"]))[:2]

  # assumes that the first price is the one to use, hopefully "all utilization practices". Might miss some double crop cases.
  cropPrices = [c["priceHistory"][0] for c in crops if c["priceHistory"]]
  topPriceChanges = sorted(cropPrices, key=lambda x: -abs(x["priceDeltaPct"]))[:2]

  return list(roundrobin([make_acre_change_chart(c) for c in topAcreChanges], [make_price_change_chart(c, CROP_YEARS[0]) for c in topPriceChanges]))

def make_crop_details_chart_data(crops):
  crop_details = {}
  for crop in crops:
    price_chart_data = []
    for price in crop["priceHistory"]:
      price_chart_data.append(make_price_change_chart(price, 0))
    crop_details[crop["name"]] = {
      "acreageChartData": make_acre_change_chart(crop),
      "priceChartData": price_chart_data,
      "priceTable": crop["priceHistory"]
    }
  return crop_details

def make_price_string(price):
  if "." in str(price):
    return "%0.2f" % float(price)
  else:
    return str(price)

def make_price_delta_string(old_price, new_price):
  if "." in str(new_price):
    return "%+0.2f" % (float(new_price) - float(old_price))
  else:
    return "%+d" % (int(new_price) - int(old_price))

def short_crop(crop_name):
  return crop_name.replace('Double Crop - ', '')

def crops_in_circle(request):
  lat = float(request.GET.get("lat"))
  lon = float(request.GET.get("lon"))
  radius = float(request.GET.get("radius"))
  location = request.GET.get("location", "US TOTAL")
  response_data = memoize(crops_in_circle_helper, {}, 4)(lat, lon, radius, location)
  response_json = json.dumps(response_data)
  return HttpResponse(response_json, content_type="application/json")

def crops_in_circle_helper(lat, lon, radius, location):
  request_json = cropscape_json(lat, lon, radius)
  cropscape_data = json.loads(fcRequest(request_json))

  # example response:
  # {"lat":[29.1462,30.348708333333335,30.551116666666665,30.753525],"lon":[-88.4743,-88.325066666666672,-88.17583333333333,-88.0266],"values":[[0.0,190.0,142.0],[0.0,142.0,142.0],[0.0,0.0,121.0]]}

  crop_table = defaultdict(lambda: defaultdict(int))
  total = 0

  lats = divider_midpoints(cropscape_data["lat"])
  lons = divider_midpoints(cropscape_data["lon"])

  for (entry_lat, row) in zip(lats, cropscape_data["values"]):
    for entry_lon, entry_crop in zip(lons, row):
      if (distance(lat, lon, entry_lat, entry_lon) < radius):
        for year, crop in zip(CROP_YEARS, entry_crop):
          crop_table[year][int(crop)] += 1
        total += 1


  crops = []
  for (crop, count) in sorted(crop_table[CROP_YEARS[-1]].items(), key=lambda x: -x[1]):
    history = []
    for year in CROP_YEARS:
      history.append(float(crop_table[year][crop]) / total)
    name = crop_name(crop)  # used in CropScape
    commodities = commodity_name(name)  # used in NASS data
    pct_acres = float(count) / total
    name = short_crop(name)
    if name and pct_acres > 0.01:  # only show crops that cover more than 1% of the area.
      pct_acres_delta = history[-1] - history[0]  # change since five years ago
      price_history = defaultdict(lambda: defaultdict(int))
      for commodity, variety in commodities:
          # only include dollar prices, not percentages of parity
        crop_prices = CropPrice.objects.filter(commodity=commodity, location=location, unit__contains="$").order_by("-year", "commodity", "variety", "util_practice")
        if variety:
          crop_prices = crop_prices.filter(variety__startswith=variety)
        for crop_price in crop_prices:
          price_history[commodity, crop_price.variety, crop_price.unit, crop_price.util_practice][crop_price.year] = crop_price.price

      price_history_list = []
      for ((commodity, variety, unit, util_practice), annual_prices) in sorted(price_history.iteritems()):
        full_crop = "%s, %s" % (commodity.capitalize(), variety.capitalize())
        if len(commodities) > 1:
          full_variety = full_crop
        else:
          full_variety = variety.capitalize()
        last_price = make_price_string(annual_prices[max(annual_prices.keys())])
        price_string = make_price_string(annual_prices[CROP_YEARS[-1]])
        price_delta = make_price_delta_string(annual_prices[CROP_YEARS[0]], annual_prices[CROP_YEARS[-1]])

        price_history_list.append({
          "shortCrop": short_crop(name),
          "crop": name,
          "fullCrop": full_crop,
          "variety": full_variety,
          "unit": str(unit).translate(None, "$/").strip().lower(),
          "utilPractice": util_practice.capitalize(),
          "price": price_string,
          "lastPrice": last_price,
          "priceDelta": price_delta,
          "priceDeltaPct": float(price_delta) / float(price_string) if float(price_string) > 0 else 0.0,
          "annualPrices": {int(key): float(value) for (key, value) in annual_prices.iteritems() if float(value) > 0}
        })

      crops.append({
        "shortName": short_crop(name),
        "name": name,
        "pctAcres": pct_acres,
        "pctAcresDelta": pct_acres_delta,
        "history": history,
        "priceHistory": price_history_list
      })

  response_data = {
    "lat": lat,
    "lon": lon,
    "radius": radius,
    "crops": crops,
    "topCropChartData": make_top_crop_chart_data(crops),
    "topTrendsChartData": make_top_trends_chart_data(crops),
    "cropDetailsChartData": make_crop_details_chart_data(crops)
  }

  return response_data

def reload_data(request):
  parsed_lines = parse_nass.load_crop_prices()
  return HttpResponse("Finished loading %s rows" % parsed_lines)
