import datetime
import math

# Hours to not run VVB ever.
hours_to_not_run = [20, 21, 22, 23]

# How many consecutive hours to run when price is at it's lowest
hours_to_run_at_bottom = 4

# How many consecutive hours to run once a day otherwise. The
# script will attempt to find the lowest price to run.
hours_to_run_otherwise = 2

# If the average price of the other cheapest hours found are
# higher than this threshold. Skip the other hours.
threshold_price_skip_other_hours = 4.5

# How many hours before it should be possible to run again.
cooldown_before_and_after_running = 6

def get_consecutive_hour_groups_larger_or_equal_size(hour_price_dict, size):
  # Create an empty dictionary to store the groups
  groups = {}

  # Iterate over the enumerated hour_price_dict
  for ix, (hour, val) in enumerate(hour_price_dict.items()):
    # Calculate the difference between the index and the value
    diff = ix - hour

    # If the difference is not already a key in the groups dictionary,
    # add it and set its value to an empty list
    if diff not in groups:
      groups[diff] = {}

    # Append the value to the list in the dictionary
    groups[diff][hour] = val

  # Return the values in the groups dictionary as a list
  return [group for group in groups.values() if len(group) >= size]

# Returns a dictionary with format { hour: price } for every
# hour in the hours-argument. Expects an array of prices.
# Filters the hours in hours_not_to_run from the returned
# array.
def get_hour_price_dict(hours, hours_to_not_run = []):
  hour_price_dict = dict(zip(range(len(hours)), hours))

  for hour in hours_to_not_run:
    if hour in hour_price_dict:
      del hour_price_dict[hour]

  return hour_price_dict

def get_cheapest_hours_for_consecutive_hour_group(hour_price_dict, size):
  combinations = [list(range(k, k+size)) for k in hour_price_dict.keys() if k+(size-1) <= max(hour_price_dict)]

  sum_hours_dict = {sum([hour_price_dict[hour] for hour in combination]): combination for combination in combinations}

  if (size > 1):
    hours_to_compare = math.floor(size / 2)

    # If the amount of hours to find is more than one, make sure we
    # find the hours where the start-hours are cheaper, since the
    # vvb will most likely utilize the first hours on more than
    # the last hours. Make sure we start at the lowest possible price.
    def get_sum_of_first_n_hours(hour):
      return sum([hour_price_dict[h] for h in sum_hours_dict[hour][:hours_to_compare]])

    # Find the 4 combinations with the lowest calculated price
    combinations_to_check = sorted(sum_hours_dict.keys())[:4]

    # Get the first n hours of each group, and check the sum of their price
    # Map to a new dictionary of { price: [all_four_hours] }
    mapped = { get_sum_of_first_n_hours(key): (key, sum_hours_dict[key]) for key in combinations_to_check}

    # Get the minimum key of the new dictionary
    min_price = min(mapped.keys())

    # Get the hours for the minimum price, this array consists of `size` hours.
    (original_min_price, min_hours) = mapped[min_price]

    return (original_min_price, min_hours)

  minimum_hours = min(sum_hours_dict.keys())

  return (minimum_hours, sum_hours_dict[minimum_hours])

# Returns (price, hours)
def get_cheapest_hours(hour_price_dict, size):
  # Split the hour_price_dict into groups of consecutive hours that
  # will be used to find a low-point
  hour_groups = get_consecutive_hour_groups_larger_or_equal_size(hour_price_dict, size)

  # Calculate the lowest price for each group
  calc_groups = [get_cheapest_hours_for_consecutive_hour_group(g, size) for g in hour_groups]

  # Find the group with the lowest price
  min_group = min(calc_groups, key = lambda g:g[0])

  # Return the hours of the group with the lowest price
  return min_group

# Takes an hour_price_dict and removes the cheapest hours from it,
# along with a cooldown on both ends.
def remove_cheapest_hours_with_cooldown_from_hour_price_dict(hour_price_dict, cheapest_total_hours, cooldown):
  negative_cooldown = cheapest_total_hours[0] - cooldown - 1
  if (negative_cooldown < 0):
    negative_cooldown = 0

  positive_cooldown = cheapest_total_hours[len(cheapest_total_hours) - 1] + cooldown + 1
  if (positive_cooldown > 23):
    positive_cooldown = 23

  cooldown_before_cheapest = list(range(cheapest_total_hours[0] - 1, negative_cooldown - 1, -1))
  cooldown_after_cheapest = list(range(cheapest_total_hours[len(cheapest_total_hours) - 1] + 1, positive_cooldown))

  for hour in cooldown_before_cheapest + cheapest_total_hours + cooldown_after_cheapest:
    if hour in hour_price_dict:
      del hour_price_dict[hour]

  return hour_price_dict

def calc_hours_to_run(price_hour_array, hours_to_run_at_bottom, hours_to_run_otherwise, cooldown, hours_to_not_run, threshold_price_skip_other_hours):
  hours_to_run = []

  hour_price_dict = get_hour_price_dict(price_hour_array, hours_to_not_run)
  (price_cheapest, cheapest_total_hours) = get_cheapest_hours(hour_price_dict, hours_to_run_at_bottom)

  log.info(f"Found cheapest hours {cheapest_total_hours} with average price {price_cheapest / len(cheapest_total_hours)}")

  hours_to_run.extend(cheapest_total_hours)
  new_hour_price_dict = remove_cheapest_hours_with_cooldown_from_hour_price_dict(hour_price_dict, cheapest_total_hours, cooldown)
  (price_other, cheapest_other_hours) = get_cheapest_hours(new_hour_price_dict, hours_to_run_otherwise)

  average_price_other_hours = price_other / len(cheapest_other_hours)

  log.info(f"Found other hours {cheapest_other_hours} with average price {average_price_other_hours}")

  if (average_price_other_hours <= threshold_price_skip_other_hours):
    hours_to_run.extend(cheapest_other_hours)
  else:
    log.info("Average price for other hours was above threshold. Not running the VVB those hours.")

  hours_to_run.sort()

  return hours_to_run

@service
@time_trigger("cron(*/45 * * * *)")
def vvb():
  log.info("Running VVB script.")

  now = datetime.datetime.now()
  current_hour = now.hour

  nordpool_sensor = sensor.nordpool_kwh_trheim_nok_3_10_025

  #Get todays prices from nordpool hacs addon. Todays prices should always be available
  today_prices = state.getattr(nordpool_sensor).get("today")

  hours_on_today = calc_hours_to_run(
    today_prices,
    hours_to_run_at_bottom,
    hours_to_run_otherwise,
    cooldown_before_and_after_running,
    hours_to_not_run,
    threshold_price_skip_other_hours)

  #Try to fetch tomorrows prices. This might fail before 14:00
  tomorrow_prices = state.getattr(nordpool_sensor).get("tomorrow")
  #If prices for tomorrow is available
  if tomorrow_prices is not None and len(tomorrow_prices) > 0 and tomorrow_prices[0] is not None:
      hours_on_tomorrow = calc_hours_to_run(
        tomorrow_prices,
        hours_to_run_at_bottom,
        hours_to_run_otherwise,
        cooldown_before_and_after_running,
        hours_to_not_run,
        threshold_price_skip_other_hours)
  else:
    hours_on_tomorrow = []

  should_be_on_now = current_hour in hours_on_today

  state.set("sensor.varmtvannsbereder_on", should_be_on_now, new_attributes ={"today_on": hours_on_today, "tomorrow_on": hours_on_tomorrow, "hours_to_not_run": hours_to_not_run})
