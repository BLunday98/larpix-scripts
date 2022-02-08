'''
Analyze LArPIX tile pedestal data using an h5 file generated from pedestal.py
Usage:
        python3 ped_stats.py <input_file> <output_file>
'''

import sys
import argparse
import json
import h5py
import numpy as np
import statistics
import requests
from datetime import datetime

_default_input_file = None
_default_output_file = None
_default_controller_config = None
_default_channels = range(64)
_default_disabled_channels = []

# Weather API helper function
def get_weather():

    # Key generated using OpenWeather API
    api_key = 'd9ed0740353b41a8f050598311c241f5'

    base_url = 'http://api.openweathermap.org/data/2.5/weather?'

    city = 'Philadelphia'

    full_url = base_url + 'appid=' + api_key + '&q=' + city

    # Send request and store response
    response = requests.get(full_url)

    # Convert JSON to python (list of dictionaries)
    pull_data = response.json()

    # 404 checking/data extraction
    if pull_data['cod'] != '404':

        # Index the main dictionary for easy reference
        main = pull_data['main']

        # Grab temp and humidity data
        temp = main['temp']
        humidity = main['humidity']

        # Write data to file
        #weather_string = ['Temperature: %i K \n ' % temp, 'Humidity: %i percent \n' %
        #humidity]
        #in_file.writelines(weather_string)

        # Spit out values for json file
        return [temp, humidity]

    # 404 error handling
    else:
        raise Exception('404 encountered in weather API')


def main(input_file=_default_input_file, output_file=_default_output_file, controller_config=_default_controller_config, channels=_default_channels, disabled_channels=_default_disabled_channels, *args, **kwargs):

    print('Pedestal statistics generated from file ' + input_file + "\n")

    now = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")

    # Write weather data to file
    try:
        weather_vals = get_weather()
    except:
        print('Exception occurred in weather request, please try again')

    # Prep python dict for later json conversion
    # Go ahead and add weather + time data
    add_dict = {'input file': input_file, 'time': now,
                'temp': weather_vals[0], 'humidity': weather_vals[1]}

    # Open specified input file
    trigger_file = h5py.File(input_file, 'r')

    # Sift out packets
    trigger_pkts = trigger_file['packets']

    # Apply bool mask to get just data packets
    trigger_data = trigger_pkts[trigger_pkts['packet_type'] == 0]

    # Storage arrays/dicts
    running_means = []
    running_vars = []
    channel_data_dict = {}

    # Remove specified channels from loop
    channels = [x for x in range(64) if x not in disabled_channels]

    # Iterate over each channel and grab pedestal mean
    for i in channels:

        # Apply bool channel mask and grab adc vals
        channel_data = trigger_data[trigger_data['channel_id'] == i]
        adc_vals = channel_data['dataword']

        # Cast adc_vals (currently int array) to floats so as to avoid weird AssertionError in stat.var/StDev
        adc_floats = adc_vals.astype(np.float)

        # Average collected values and write to File
        adc_mean = statistics.mean(adc_floats)
        sigma = statistics.stdev(adc_floats)
        variance = statistics.variance(adc_floats)

        # Cast channel name to string for dict formatting
        channel_name = '% i' % i
        channel_label = str(channel_name)
        mean_label = 'mean_' + channel_label
        sigma_label = 'sigma_' + channel_label

        # Create channel data dict
        ch_dict = {channel_label: i, mean_label: adc_mean, sigma_label: sigma}
        channel_data_dict.update(ch_dict)
        add_dict.update(channel_data_dict)

        # Append these values for later tile calcs
        running_means.append(adc_mean)
        running_vars.append(sigma)

    # Calculate whole tile statistics
    whole_mean = statistics.mean(running_means)
    whole_dev = np.sqrt(np.sum(running_vars))

    #whole_tile_stats = {'mean adc reading': whole_mean, 'total stdev': whole_dev}
    add_dict['mean adc reading'] = whole_mean
    add_dict['total stdev'] = whole_dev

    with open(output_file, 'w') as j_file:
        dict = json.dumps(add_dict, indent=4)
        j_file.write(dict)


print('End Stats')

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--input_file',
                        type=str, help='h5 file generated using pedestal.py')
    parser.add_argument('--output_file', type=str,
                        help='Name for output data file')
    parser.add_argument('--controller_config', default=_default_controller_config,
                        type=str, help='''Hydra network configuration file''')
    parser.add_argument('--channels', default=_default_channels, type=json.loads,
                        help='''List of channels to collect data from (json formatting)''')
    parser.add_argument('--disabled_channels', default=_default_disabled_channels,
                        type=json.loads, help='''List of channels to disable in dict format''')
    args = parser.parse_args()
    c = main(**vars(args))
