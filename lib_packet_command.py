#file      lin_packet_command.py

#brief      mac command decoder

#Revised BSD License

#Copyright Semtech Corporation 2020. All rights reserved.

#Redistribution and use in source and binary forms, with or without
#modification, are permitted provided that the following conditions are met:
#Redistributions of source code must retain the above copyright
#notice, this list of conditions and the following disclaimer.
#Redistributions in binary form must reproduce the above copyright
#notice, this list of conditions and the following disclaimer in the
#documentation and/or other materials provided with the distribution.
#Neither the name of the Semtech corporation nor the
#names of its contributors may be used to endorse or promote products
#derived from this software without specific prior written permission.


#THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
#AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
#IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
#ARE DISCLAIMED. IN NO EVENT SHALL SEMTECH CORPORATION. BE LIABLE FOR ANY DIRECT,
#INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
#(INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
#LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
#ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
#(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
#SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

def MacCommandDecoder(MACCommand, direction):
    commands = []
    if direction: # uplink #
        while MACCommand:
            if MACCommand == "02":
                command = {"Command": "LinkCheckReq", 
                           "LinkCheckReq": None}
                commands.append(command)
                MACCommand = MACCommand[2:]
                continue
            if MACCommand[:2] == "03":
                status_bin = bin(int(MACCommand[2:4], 16))[2:].zfill(8)
                command = {"Command": "LinkADRAns", 
                           "Status": MACCommand[2:4], 
                           "Power ACK": status_bin[5]=='1', 
                           "Data rate ACK": status_bin[6]=='1', 
                           "Channel mask ACK": status_bin[7]=='1'}
                commands.append(command)
                MACCommand = MACCommand[4:]
                continue
            if MACCommand[:2] == "05":
                status_bin = bin(int(MACCommand[2:4], 16))[2:].zfill(8)
                command = {"Command": "RXParamSetupAns",
                           "Status": MACCommand[2:4],
                           "RX1DRoffset ACK": bool(int(status_bin[5])),
                           "RX2 Data rate ACK": bool(int(status_bin[6])),
                           "Channel ACK": bool(int(status_bin[7]))}
                commands.append(command)
                MACCommand = MACCommand[4:]
                continue
            if MACCommand[:2] == "06":
                Margin_bin = bin(int(MACCommand[4:6], 16))[2:].zfill(8)
                command = {"Command": "DevStatusAns",
                           "Battery": int(MACCommand[2:4], 16),
                           "Margin": int(Margin_bin[2:8], 2), 
                           "DevStatusAns": True}
                commands.append(command)
                MACCommand = MACCommand[6:]
                continue
            if MACCommand[:2] == "07":
                status_bin = bin(int(MACCommand[2:4], 16))[2:].zfill(8)
                command = {"Command": "NewChannelAns",
                           "Status": MACCommand[2:4], 
                           "Data_rate_range_ok": bool(int(status_bin[6])),
                           "Channel_frequency_ok": bool(int(status_bin[7])),
                           "NewChannelAns": None
                }
                commands.append(command)
                MACCommand = MACCommand[4:]
                continue
            if MACCommand[:2] == "08":
                command = {"Command": "RXTimingSetupAns", 
                           "RXTimingSetupAns": True}
                commands.append(command)
                MACCommand = MACCommand[2:]
                continue
            if MACCommand[:2] == "09":
                command = {"Command": "TxParamSetupAns", 
                           "TxParamSetupAns": None}
                commands.append(command)
                MACCommand = MACCommand[2:]
    else:
        while MACCommand:
            if MACCommand == "02":
                command = {"Command": "LinkCheckAns)",
                           "Margin": int(MACCommand[2:4], 16),
                           "GwCnt": int(MACCommand[4:6], 16)}
                commands.append(command)
                MACCommand = MACCommand[6:]
                continue
            if MACCommand[:2] == "03":
                Redundancy_bin = bin(int(MACCommand[8:10], 16))[2:].zfill(8)
                command = {"Command": "LinkADRReq", 
                           "DataRate_TXPower": int(MACCommand[2:4], 16), 
                           "DataRate": int(MACCommand[2], 16), 
                           "TXPower": int(MACCommand[3], 16), 
                           "ChMask": bin(int(MACCommand[4:8], 16))[2:].zfill(16), 
                           "Redundancy": MACCommand[8:10], 
                           "ChMaskCntl": int(Redundancy_bin[1:4], 2), 
                           "NbTrans": int(Redundancy_bin[4:8], 2), 
                           } 
                commands.append(command)
                MACCommand = MACCommand[10:]
                continue
            if MACCommand[:2] == "05":
                DLsettings_bin = bin(int(MACCommand[2:4], 16))[2:].zfill(8)
                command = {"Command": "RXParamSetupReq",
                           "DLsettings": MACCommand[2:4],
                           "Frequency": int(MACCommand[8:10] + MACCommand[6:8] + MACCommand[4:6], 16), 
                           "RX1DRoffset": int(DLsettings_bin[1:4], 2),
                           "RX2DataRate": int(DLsettings_bin[4:8], 2)}
                commands.append(command)
                MACCommand = MACCommand[10:]
                continue
            if MACCommand[:2] == "06":
                command = {"Command": "DevStatusReq", 
                           "DevStatusReq": None}
                commands.append(command)
                MACCommand = MACCommand[2:]
                continue
            
            if MACCommand[:2] == "07":
                command = {"Command": "NewChannelReq",
                           "ChIndex": int(MACCommand[2:4], 16),
                           "Freq": int(MACCommand[8:10] + MACCommand[6:8] + MACCommand[4:6], 16), 
                           "DrRange": MACCommand[10:12], 
                           "NewChannelReq": None
                }
                commands.append(command)
                MACCommand = MACCommand[12:]
                continue

            if MACCommand[:2] == "08":
                Settings_bin = bin(int(MACCommand[2:4], 16))[2:].zfill(8)
                command = {"Command": "RXTimingSetupReq",
                           "Del": int(Settings_bin[4:8], 2)}
                commands.append(command)
                MACCommand = MACCommand[4:]
                continue
            if MACCommand[:2] == "09":
                EIRP_DwellTime_bin = bin(int(MACCommand[2:4], 16))[2:].zfill(8)
                command = {"Command": "TxParamSetupReq",
                           "DownlinkDwellTime": bool(int(EIRP_DwellTime_bin[2])),
                           "UplinkDwellTime": bool(int(EIRP_DwellTime_bin[3])),
                           "MaxEIRP": int(EIRP_DwellTime_bin[4:8], 2)}
                commands.append(command)
                MACCommand = MACCommand[4:]
                continue
    return commands

