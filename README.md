# DBC-2-CPP-py
This is a fork https://github.com/jobgeodev/convert_dbc_to_cpp_file. The script is a wrapper around generate_c_source from cantools, so you can just pass the received can message into a PARSE_ function and get the individual signals back.
It contains a few changes to make it Arduino compatible, so you can use it in combination with autowp's MCP2515 library (https://github.com/autowp/arduino-mcp2515).
It also contains bugfixes and a generic cli interface. A good source for DBC files is https://github.com/commaai/opendbc.


### 1.  Install cantools
```
pip install cantools
```

### 2.  Example use

Assuming the following folder structure:

```
.
├── DBC-2-CPP-py
├─────── build_dbc_cpp_code.py
├── CAN-generated                    
├─────── gm_global_a_powertrain.dbc
├─────── <generated .c and .h files>
```

```
python build_dbc_cpp_code.py ..\CAN-generated\gm_global_a_powertrain.dbc --o ..\CAN-generated -p GM_LAN

```

You should see:
```
Successfully generated ..\CAN-generated\gm_global_a_powertrain.h and ..\CAN-generated\gm_global_a_powertrain.c.
```

Usage in code:
```
struct can_frame currentFrame;

if (m_mcp2515.readMessage(&currentFrame) == MCP2515::ERROR_OK)
{
        T_ECM_ENGINE_STATUS data{};
        int returnCode = PARSE_ECM_ENGINE_STATUS(currentFrame, data);
        if (returnCode == 0)
        {            
         Serial.println(data.ENGINE_RPM);
         Serial.println(data.ENGINE_TPS);
        }
}
```
