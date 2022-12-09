import datetime

# Hours to not run VVB ever.
ignore_hours = [15, 21, 22, 23]

# How many hours to run when price is at it's lowest
hours_on_at_bottom = 4
hours_on_otherwise = 2

# How many hours before it should be possible to run again.
cooldown = 6

def get_consecutive_hour_groups(hour_price_dict):
  # Create an empty dictionary to store the groups
  groups = {}

  # Iterate over the enumerated hour_price_dict
  for ix, val in enumerate(hour_price_dict):
    # Calculate the difference between the index and the value
    diff = ix - val

    # If the difference is not already a key in the groups dictionary,
    # add it and set its value to an empty list
    if diff not in groups:
      groups[diff] = []

    # Append the value to the list in the dictionary
    groups[diff].append(val)

  # Return the values in the groups dictionary as a list
  return list(groups.values())

def get_hour_price_dict(hours, ignore_hours = []):
  hour_price_dict = dict(zip(range(len(hours)), hours))

  for hour in ignore_hours:
    if hour in hour_price_dict:
      del hour_price_dict[hour]

  return hour_price_dict

def get_cheapest_hours_for_group(hour_price_dict, size):
  combinations = [list(range(k, k+size)) for k in hour_price_dict.keys() if k+(size-1) <= max(hour_price_dict)]

  sum_hours_dict = {sum([hour_price_dict[hour] for hour in combination]): combination for combination in combinations}

  minimum_hours = min(sum_hours_dict.keys())

  return (minimum_hours, sum_hours_dict[minimum_hours])

def get_cheapest_hours(hour_price_dict, size):
  hour_groups = get_consecutive_hour_groups(hour_price_dict)

  mapped_groups = [{hour:hour_price_dict[hour] for hour in group} for group in hour_groups if len(group) >= size]

  calc_groups = [get_cheapest_hours_for_group(g, size) for g in mapped_groups]

  min_group = min(calc_groups, key = lambda g:g[0])

  return min_group[1]

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

def calc_hours_on(price_hour_array, hours_on_at_bottom, hours_on_otherwise, cooldown, ignore_hours):
  hours_on = []

  hour_price_dict = get_hour_price_dict(price_hour_array, ignore_hours)
  cheapest_total_hours = get_cheapest_hours(hour_price_dict, 4)
  hours_on.extend(cheapest_total_hours)
  new_hour_price_dict = remove_cheapest_hours_with_cooldown_from_hour_price_dict(hour_price_dict, cheapest_total_hours, cooldown)
  cheapest_other_hours = get_cheapest_hours(new_hour_price_dict, 2)
  hours_on.extend(cheapest_other_hours)
  hours_on.sort()

  return hours_on

@service
@time_trigger("cron(*/2 * * * *)")
def vvb():
  log.info("Running VVB script.")

  now = datetime.datetime.now()
  current_hour = now.hour

  nordpool_sensor = sensor.nordpool_kwh_trheim_nok_3_10_025

  #Get todays prices from nordpool hacs addon. Todays prices should always be available
  today_prices = state.getattr(nordpool_sensor).get("today")

  hours_on_today = calc_hours_on(today_prices, hours_on_at_bottom, hours_on_otherwise, cooldown, ignore_hours)

  #Try to fetch tomorrows prices. This might fail before 14:00
  tomorrow_prices = state.getattr(nordpool_sensor).get("tomorrow")
  #If prices for tomorrow is available
  if len(tomorrow_prices) > 0 and tomorrow_prices[0] is not None:
      hours_on_tomorrow = calc_hours_on(tomorrow_prices, hours_on_at_bottom, hours_on_otherwise, cooldown, ignore_hours)

  state.set("sensor.varmtvannsbereder_on", current_hour in hours_on_today, new_attributes ={"today_on": hours_on_today, "tomorrow_on": hours_on_tomorrow})
