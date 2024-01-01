import datetime

@time_trigger("cron(*/2 * * * *)")
def update_saving_hours():
  now = datetime.datetime.now()
  current_hour = now.hour

  log.info("Running power saving script at %s" % now)

  nordpool_sensor = sensor.nordpool

  #Get todays prices from nordpool hacs addon. Todays prices should always be available
  today_prices = state.getattr(nordpool_sensor).get("today")
  hour_price_pairs = zip(range(24), today_prices)
  hour_price_pairs = sorted(hour_price_pairs, key=lambda v: v[1])

  #Create a lookup table from hour to index. Index of 0 is the least expensive hour, 23 the most.
  most_expensive_today = {}
  for i,(hour, price) in enumerate(hour_price_pairs):
      most_expensive_today[hour] = i

  #Try to fetch tomorrows prices. This might fail before 14:00
  tomorrow_prices = state.getattr(nordpool_sensor).get("tomorrow")

  #If prices for tomorrow is available
  if len(tomorrow_prices) > 0 and tomorrow_prices[0] is not None:
      hour_price_pairs = zip(range(24), tomorrow_prices)
      hour_price_pairs = sorted(hour_price_pairs, key=lambda v: v[1])

      most_expensive_tomorrow = {}
      for i,(hour, price) in enumerate(hour_price_pairs):
          most_expensive_tomorrow[hour] = i

  #Generate 23 sensors for least and most expensive hours of the day
  for i in range(1,24):
      #Generate schedule attribute for today
      least_n_expensive = [{"price": today_prices[v], "hour": v, "state": most_expensive_today[v] < i} for v in range(0,24)]

      #If tomorows prices are available, generate schedule for tomorrow.
      if len(tomorrow_prices) > 0 and tomorrow_prices[0] is not None:
          least_n_expensive_tomorrow = [{"price": tomorrow_prices[v], "hour": v, "state": most_expensive_tomorrow[v] < i} for v in range(0,24)]
      else:
          least_n_expensive_tomorrow = []

      #Set the new state of the sensor
      state.set("sensor.powersaving_%s_least_expensive" %i, most_expensive_today[current_hour] < i, new_attributes={"today_prices": today_prices, "today": least_n_expensive, "tomorrow_prices": tomorrow_prices, "tomorrow": least_n_expensive_tomorrow})#, new_attributes={"hours": })

      #Generate schedule for most expensive hours today
      n_most_expensive = [{v: most_expensive_today[v] > 23-i} for v in range(0,24)]

      #If tomorrows prices are available, generate schedule for tomorrow
      if len(tomorrow_prices) > 0 and tomorrow_prices[0] is not None:
          n_most_expensive_tomorrow = [{v: most_expensive_tomorrow[v] > 23-i} for v in range(0,24)]
      else:
          n_most_expensive_tomorrow = []

      #Set the new state of the sensor
      state.set("sensor.powersaving_%s_most_expensive" %i, most_expensive_today[current_hour] > 23-i, new_attributes={"today_prices": today_prices, "today": n_most_expensive, "tomorrow_prices": tomorrow_prices, "tomorrow": n_most_expensive_tomorrow})#, new_attributes={"hours:": map(lambda v: most_expensive[current_hour] >= i, range(0,24))})
