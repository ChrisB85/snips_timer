#!/usr/bin/env python3
from hermes_python.hermes import Hermes
from hermes_python.ontology import *
import random, os, sys, io, time, json, datetime
import snips_common as sc
import snips_timer as st
import mqtt_client
from pprint import pprint

intents = mqtt_client.get_config().get('global', 'intent').split(",")
INTENT_FILTER_START_SESSION = []
for x in intents:
    INTENT_FILTER_START_SESSION.append(x.strip())

prefix = mqtt_client.get_config().get('global', 'prefix')

#t = st.fix_time('siódmej 5')
#print(t)
#test = datetime.datetime.strptime(t, "%H:%M")
#print(test)

# Check existing timers
st.check_timers(True)
st.check_alarms(True)

def get_intent_site_id(intent_message):
    return intent_message.site_id


def get_intent_msg(intent_message):
    return intent_message.intent.intent_name.split(':')[-1]


def start_session(hermes, intent_message):
    print("Timer session_start")
    session_id = intent_message.session_id
    site_id = get_intent_site_id(intent_message)
    locations = st.get_locations(intent_message)
    if len(locations) >= 1:
        site_id = locations[0]
    target = ''
    targets = st.get_targets(intent_message)
    #pprint(targets)

    if len(targets) > 0:
        target = targets[0]
    intent_msg_name = get_intent_msg(intent_message)

    print("Starting device control session " + session_id)

    intent_slots = st.get_intent_slots(intent_message)
    time_units = st.get_time_units(intent_message)
    hours = st.get_hours(intent_message)
    if len(hours) > 0:
        alarm_time_str = datetime.datetime.today().strftime('%Y-%m-%d ') + st.fix_time(hours[0])
        alarm_datetime = datetime.datetime.strptime(alarm_time_str, "%Y-%m-%d %H:%M")
        if datetime.datetime.timestamp(alarm_datetime) < datetime.datetime.timestamp(datetime.datetime.now()):
            next_date = alarm_datetime + datetime.timedelta(days=1)
            hour = next_date.strftime("%Y-%m-%d %H:%M")
            hour_only = next_date.strftime("%H:%M")
        else:
            hour = alarm_datetime.strftime("%Y-%m-%d %H:%M")
            hour_only = alarm_datetime.strftime("%H:%M")
    else:
        hour = ''
        hour_only = ''

    if len(intent_slots) < len(time_units):
        intent_slots.insert(0, 1)
    # Get seconds amount
    total_amount = 0
    for key, value in enumerate(intent_slots):
        try:
            amount = float(st.get_intent_amount(value))
        except ValueError:
            print("Error: That's not an float!")
            hermes.publish_end_session(session_id, "Przepraszam, nie zrozumiałem")
            return
        total_amount = amount * st.get_unit_multiplier(time_units[key]) + total_amount

    if intent_msg_name == 'countdown':
        hermes.publish_end_session(session_id, None)

        end_time = int((time.time() * 1000) + (total_amount * 1000))

        # Add new timer
        st.add_timer(site_id, total_amount, end_time, target)

        # Call timer
        st.call_timer(site_id, total_amount, end_time, target)

        # Say
        amount_say = st.get_amount_say(total_amount)
        say = ['Rozpoczynam odliczanie', 'Czas start!', 'Odliczam', 'Robi się']
        amount_say.append(random.choice(say))
        for text in amount_say:
            sc.put_notification(site_id, text)
            time.sleep(0.2)

    if intent_msg_name == 'countdown_interrupt' or intent_msg_name == 'countdown_left':
        hermes.publish_end_session(session_id, None)
        if len(intent_slots) == 0 or len(time_units) == 0:
            mqtt_client.put('timer/' + intent_msg_name + '/' + site_id, 0)
        else:
            mqtt_client.put('timer/' + intent_msg_name + '/' + site_id, int(total_amount))

    if intent_msg_name == 'alarm' and len(hours) > 0:
        hermes.publish_end_session(session_id, None)
        st.add_alarm(site_id, hour, target)
        st.call_alarm(site_id, hour, target)
        say = ['OK, godzina', 'Jasne, godzina', 'Planuję alarm, godzina', 'Dobrze, godzina']
        alarm_say = random.choice(say)
        alarm_say = alarm_say + " " + hour_only
        sc.put_notification(site_id, alarm_say)

    if intent_msg_name == 'alarm_interrupt':
       mqtt_client.put('timer/' + intent_msg_name + '/' + site_id, hour)


with Hermes(mqtt_options = sc.get_hermes_mqtt_options()) as h:
    for a in INTENT_FILTER_START_SESSION:
        h.subscribe_intent(prefix + a, start_session)
    h.start()
