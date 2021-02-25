# Snoo for Home Assistant
This is a [Home Assistant](https://home-assistant.io/) custom component to retreive the status of your [SNOO Smart Bassinet](https://www.happiestbaby.com/). It creates a binary_sensor indicating if the snoo is active. And a sensor entity showing the current session state.

This component uses python module [pysnooapi](https://pypi.org/project/pysnooapi/).

> Note:
It is not possible to send commands. The python module only provides access to Snoo's unofficial readonly API.


## Installation
### Easy Mode
[Use HACS](https://github.com/custom-components/alexa_media_player/wiki#automatic-updates). This will also inform you when there are new releases and you can update easily. If installed this way, you can proceed to configuration using the Integrations Page.

### Manual Mode
Copy the custom_components/alexa_media directory from the latest release to your customer_components directory and restart Home Assistant.

## Configure HA

The component can be configured via the Integrations page in HA.

1. Goto the Configuration -> Integrations page.
2. On the bottom right of the page, click on the Orange + sign to add an integration.
3. Search for Snoo. (If you don't see it, try refreshing your browser page to reload the cache.)
4. Enter the required information. (Email/Password)
5. No reboot is required. You can relogin or change the password/settings by deleting and re-adding on this page without impacting any automations/scripts.

## Usage
If successful, the component adds a new `sensor.<baby_name>_s_snoo` sensor and `binary_sensor.<baby_name>_s_snoo`.

### Binary sensor
#### State
* `on`: when the snoo is on and there is an active session
* `off`: when there is no active session

### Sensor
#### State
* `ONLINE`: The session is not active
* `WEANING_BASELINE`: Session is active and the baseline is no motion when weaning mode is turned on
* `BASELINE`: Baseline level
* `LEVEL1`: Level 1
* `LEVEL2`: Level 2
* `LEVEL3`: Level 3
* `LEVEL4`: Level 4
#### Attributes
* Session:
  * startTime: start time for current or last session
  * endTime: end time for last session. None if a session is active
  * levels: sequence of levels in current session in chronological order. (Last level is the latest)


## Uninstalling Integration
If you wish to uninstall this integration, you can click Uninstall on the component in HACS. You must also remove the integration from your Integrations page, under Configuration > Integrations. If you do not complete this last step, you will get an error message every time you restart Home Assistant that says 'error setting up snoo'.
