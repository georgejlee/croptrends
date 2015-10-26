from models import CropPrice
import csv
import sys
from django.db import IntegrityError

NASS_PREFIX = "/Users/george/usda/NASS"
COMMODITY_VALUE_FILE = NASS_PREFIX + "/CommodityValue.csv"
STATISTIC_CATEGORY_FILE = NASS_PREFIX + "/Statisticcat.csv"
COMMODITY_FILE = NASS_PREFIX + "/Commodity.csv"
CLASS_FILE = NASS_PREFIX + "/Class.csv"
UNIT_FILE = NASS_PREFIX + "/Unit.csv"
UTIL_PRACTICE_FILE = NASS_PREFIX + "/UtilPractice.csv"

def load_id_name_table(filename):
  table = {}
  table_index = {}
  with open(filename) as csvfile:
    reader = csv.reader(csvfile, delimiter = ';')
    header_row = reader.next()
    for id, name in reader:
      table[int(id)] = name
      table_index[name] = int(id)
  return (table, table_index)

def load_crop_prices():
  statistic_category, statistic_category_index = load_id_name_table(STATISTIC_CATEGORY_FILE)
  commodity, commodity_index = load_id_name_table(COMMODITY_FILE)
  unit, unit_index = load_id_name_table(UNIT_FILE)
  commodity_class, commodity_class_index = load_id_name_table(CLASS_FILE)
  util_practice, util_practice_index = load_id_name_table(UTIL_PRACTICE_FILE)

  with open(COMMODITY_VALUE_FILE) as csvfile:
    commodity_value_reader = csv.reader(csvfile, delimiter = ';')
    line_number = 0
    saved_rows = 0
    header_row = commodity_value_reader.next()
    print ', '.join(header_row)
    col_index = {}
    for i, col in enumerate(header_row):
      col_index[col] = i

    for line in commodity_value_reader:
      if (int(line[col_index['StatisticcatId']]) == statistic_category_index['PRICE RECEIVED'] and
#          unit[int(line[col_index['UnitId']])] != 'PCT OF PARITY' and
          line[col_index['REFERENCE_PERIOD_DESC']] == 'MARKETING YEAR'):

        # Some commodities have weekly prices, like milk and cheese.
        # Most vegetables are priced by marketing year, but milk and wool (and others) are not.

        output = line
        output[col_index['CommodityId']] = commodity[int(output[col_index['CommodityId']])]
        output[col_index['UnitId']] = unit[int(output[col_index['UnitId']])]
        output[col_index['ClassId']] = commodity_class[int(output[col_index['ClassId']])]
        output[col_index['UtilPracticeId']] = util_practice[int(output[col_index['UtilPracticeId']])]
        output_cols = ['CommodityId', 'ClassId', 'UtilPracticeId', 'LOCATION_DESC', 'YEAR', 'VALUE_NUM', 'UnitId']
        crop_price = CropPrice()
        crop_price.commodity = output[col_index['CommodityId']]
        crop_price.location = output[col_index['LOCATION_DESC']]
        crop_price.year = int(output[col_index['YEAR']])
        crop_price.variety = output[col_index['ClassId']]
        crop_price.price = output[col_index['VALUE_NUM']]
        crop_price.unit = output[col_index['UnitId']]
        crop_price.util_practice = output[col_index['UtilPracticeId']]

        DEBUG = False
        if DEBUG:
          output_parts = []
          for col_name in output_cols:
            output_parts.append(output[col_index[col_name]])
          print ', '.join(line), '...', ' | '.join(output_parts)
        else:
          try:
            crop_price.save()
            if (saved_rows % 1000) == 0:
              print 'o',
              sys.stdout.flush()
            saved_rows += 1
          except IntegrityError:
            output_parts = []
            for col_name in output_cols:
              output_parts.append(output[col_index[col_name]])
            print 'Duplicate data: ', ', '.join(line), '...', ' | '.join(output_parts)
      else:
        if (line_number % 100000) == 0:
          print '.',
          sys.stdout.flush()

      line_number += 1

    print
    return saved_rows