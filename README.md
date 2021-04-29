# LoRaWAN conformance testbed

The project for LoRaWAN conformance testbed

v1.0.0 released on April 30, 2020

v1.1.0 released on April 29, 2021. Read release notes for changes information.

## Objective

The goal of this test bed is to enable the testing and pre-certification of sensors at the developer’s site, operating under normal operation modes or test mode applications. This all-in-one software and hardware package will be developed with an easy interface for developers to validate their hardware and firmware design and quality. 

### Basic Information

- Layers to be tested/qualified: MAC and application layer. 
- Support test interruption and recovery: the test duration can be long, so the testbed should be able to recover from the previous state in the presence of power outage or internet outage. 
- Support multiple DUT to be tested at the same time. 
- Qualification layers
    - LoRaWAN MAC implementation, basic functionality
    - LoRaWAN MAC implementation, robustness
    - Sensor application layer design
    - Sensor application layer robustness
    - Power consumption during long-term operation, in status, including but not limited to transmission, reception, and sleeping. 

### Functionality to be Evaluated

- Over the Air Activation: pre-joining behaviors
- MAC Command Verification: DUT response to typical MAC commands from the network. 
- Normal Operation: DUT normal operation, power consumption, and stability.
- Application Layer Robustness: DUT behavior with high PER, frequency selective channels and other corner cases. 
