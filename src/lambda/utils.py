def timedelta_formatter(td):
    td_sec = td.seconds
    hour_count, rem = divmod(td_sec, 3600)
    hour_count += td.days * 24
    minute_count, second_count = divmod(rem, 60)
    return f'{hour_count}h, {minute_count}min, {second_count}s'
