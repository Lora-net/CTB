/*
file      ads1256_driver.c

brief		current consumption driver  code

Revised BSD License

Copyright Semtech Corporation 2020. All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:
Redistributions of source code must retain the above copyright
notice, this list of conditions and the following disclaimer.
Redistributions in binary form must reproduce the above copyright
notice, this list of conditions and the following disclaimer in the
documentation and/or other materials provided with the distribution.
Neither the name of the Semtech corporation nor the
names of its contributors may be used to endorse or promote products
derived from this software without specific prior written permission.


THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
ARE DISCLAIMED. IN NO EVENT SHALL SEMTECH CORPORATION. BE LIABLE FOR ANY DIRECT,
INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
(INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
*/
/*
 * ADS1256_test.c:
 *	Very simple program to test the serial port. Expects
 *	the port to be looped back to itself
 *
 */

/*
             define from bcm2835.h                       define from Board DVK511
                 3.3V | | 5V               ->                 3.3V | | 5V
    RPI_V2_GPIO_P1_03 | | 5V               ->                  SDA | | 5V
    RPI_V2_GPIO_P1_05 | | GND              ->                  SCL | | GND
       RPI_GPIO_P1_07 | | RPI_GPIO_P1_08   ->                  IO7 | | TX
                  GND | | RPI_GPIO_P1_10   ->                  GND | | RX
       RPI_GPIO_P1_11 | | RPI_GPIO_P1_12   ->                  IO0 | | IO1
    RPI_V2_GPIO_P1_13 | | GND              ->                  IO2 | | GND
       RPI_GPIO_P1_15 | | RPI_GPIO_P1_16   ->                  IO3 | | IO4
                  VCC | | RPI_GPIO_P1_18   ->                  VCC | | IO5
       RPI_GPIO_P1_19 | | GND              ->                 MOSI | | GND
       RPI_GPIO_P1_21 | | RPI_GPIO_P1_22   ->                 MISO | | IO6
       RPI_GPIO_P1_23 | | RPI_GPIO_P1_24   ->                  SCK | | CE0
                  GND | | RPI_GPIO_P1_26   ->                  GND | | CE1

::if your raspberry Pi is version 1 or rev 1 or rev A
RPI_V2_GPIO_P1_03->RPI_GPIO_P1_03
RPI_V2_GPIO_P1_05->RPI_GPIO_P1_05
RPI_V2_GPIO_P1_13->RPI_GPIO_P1_13
::
*/

#include <bcm2835.h>
#include <stdio.h>
#include <unistd.h>
#include <string.h>
#include <math.h>
#include <errno.h>
#include <time.h>
#include <sys/time.h>
#include <sys/types.h>
#include <sys/stat.h>


#include <stdlib.h>
#include <unistd.h>
#include <fcntl.h>

//CS      -----   SPICS
//DIN     -----   MOSI
//DOUT  -----   MISO
//SCLK   -----   SCLK
//DRDY  -----   ctl_IO     data  starting
//RST     -----   ctl_IO     reset



//#define  DRDY  RPI_V2_GPIO_P1_11         //P0
#define  DRDY  17
//#define  RST  RPI_V2_GPIO_P1_12     //P1
#define  RST  18
//#define	SPICS	RPI_V2_GPIO_P1_15	//P3
#define  SPICS  22

#define CS_1() bcm2835_gpio_write(SPICS,HIGH)
#define CS_0()  bcm2835_gpio_write(SPICS,LOW)

#define DRDY_IS_LOW()	((bcm2835_gpio_lev(DRDY)==0))

#define RST_1() 	bcm2835_gpio_write(RST,HIGH)
#define RST_0() 	bcm2835_gpio_write(RST,LOW)



/* Unsigned integer types  */
#define uint8_t unsigned char
#define uint16_t unsigned short
#define uint32_t unsigned long

/* Type safe max macro */
#define max(a,b) \
   ({ __typeof__ (a) _a = (a); \
      __typeof__ (b) _b = (b); \
      _a > _b ? _a : _b; })


typedef enum {FALSE = 0, TRUE = !FALSE} bool;


/* gain channel� */
typedef enum
{
    ADS1256_GAIN_1			= (0),	/* GAIN   1 */
    ADS1256_GAIN_2			= (1),	/*GAIN   2 */
    ADS1256_GAIN_4			= (2),	/*GAIN   4 */
    ADS1256_GAIN_8			= (3),	/*GAIN   8 */
    ADS1256_GAIN_16			= (4),	/* GAIN  16 */
    ADS1256_GAIN_32			= (5),	/*GAIN    32 */
    ADS1256_GAIN_64			= (6),	/*GAIN    64 */
} ADS1256_GAIN_E;

/* Sampling speed choice*/
/*
	11110000 = 30,000SPS (default)
	11100000 = 15,000SPS
	11010000 = 7,500SPS
	11000000 = 3,750SPS
	10110000 = 2,000SPS
	10100001 = 1,000SPS
	10010010 = 500SPS
	10000010 = 100SPS
	01110010 = 60SPS
	01100011 = 50SPS
	01010011 = 30SPS
	01000011 = 25SPS
	00110011 = 15SPS
	00100011 = 10SPS
	00010011 = 5SPS
	00000011 = 2.5SPS
*/
typedef enum
{
    ADS1256_30000SPS = 0,
    ADS1256_15000SPS,
    ADS1256_7500SPS,
    ADS1256_3750SPS,
    ADS1256_2000SPS,
    ADS1256_1000SPS,
    ADS1256_500SPS,
    ADS1256_100SPS,
    ADS1256_60SPS,
    ADS1256_50SPS,
    ADS1256_30SPS,
    ADS1256_25SPS,
    ADS1256_15SPS,
    ADS1256_10SPS,
    ADS1256_5SPS,
    ADS1256_2d5SPS,

    ADS1256_DRATE_MAX
} ADS1256_DRATE_E;

#define ADS1256_DRAE_COUNT = 15;

typedef struct
{
    ADS1256_GAIN_E Gain;		/* GAIN  */
    ADS1256_DRATE_E DataRate;	/* DATA output  speed*/
    int32_t AdcNow[8];			/* ADC  Conversion value */
    uint8_t Channel;			/* The current channel*/
    uint8_t ScanMode;	/*Scanning mode,   0  Single-ended input  8 channel�� 1 Differential input  4 channel*/
} ADS1256_VAR_T;



/*Register definition�� Table 23. Register Map --- ADS1256 datasheet Page 30*/
enum
{
    /*Register address, followed by reset the default values */
    REG_STATUS = 0,	// x1H
    REG_MUX    = 1, // 01H
    REG_ADCON  = 2, // 20H
    REG_DRATE  = 3, // F0H
    REG_IO     = 4, // E0H
    REG_OFC0   = 5, // xxH
    REG_OFC1   = 6, // xxH
    REG_OFC2   = 7, // xxH
    REG_FSC0   = 8, // xxH
    REG_FSC1   = 9, // xxH
    REG_FSC2   = 10, // xxH
};

/* Command definition�� TTable 24. Command Definitions --- ADS1256 datasheet Page 34 */
enum
{
    CMD_WAKEUP  = 0x00,	// Completes SYNC and Exits Standby Mode 0000  0000 (00h)
    CMD_RDATA   = 0x01, // Read Data 0000  0001 (01h)
    CMD_RDATAC  = 0x03, // Read Data Continuously 0000   0011 (03h)
    CMD_SDATAC  = 0x0F, // Stop Read Data Continuously 0000   1111 (0Fh)
    CMD_RREG    = 0x10, // Read from REG rrr 0001 rrrr (1xh)
    CMD_WREG    = 0x50, // Write to REG rrr 0101 rrrr (5xh)
    CMD_SELFCAL = 0xF0, // Offset and Gain Self-Calibration 1111    0000 (F0h)
    CMD_SELFOCAL= 0xF1, // Offset Self-Calibration 1111    0001 (F1h)
    CMD_SELFGCAL= 0xF2, // Gain Self-Calibration 1111    0010 (F2h)
    CMD_SYSOCAL = 0xF3, // System Offset Calibration 1111   0011 (F3h)
    CMD_SYSGCAL = 0xF4, // System Gain Calibration 1111    0100 (F4h)
    CMD_SYNC    = 0xFC, // Synchronize the A/D Conversion 1111   1100 (FCh)
    CMD_STANDBY = 0xFD, // Begin Standby Mode 1111   1101 (FDh)
    CMD_RESET   = 0xFE, // Reset to Power-Up Values 1111   1110 (FEh)
};


ADS1256_VAR_T g_tADS1256;
static const uint8_t s_tabDataRate[ADS1256_DRATE_MAX] =
{
    0xF0,		/*reset the default values  */
    0xE0,
    0xD0,
    0xC0,
    0xB0,
    0xA1,
    0x92,
    0x82,
    0x72,
    0x63,
    0x53,
    0x43,
    0x33,
    0x20,
    0x13,
    0x03
};







void  bsp_DelayUS(uint64_t micros);
void ADS1256_StartScan(uint8_t _ucScanMode);
static void ADS1256_Send8Bit(uint8_t _data);
void ADS1256_CfgADC(ADS1256_GAIN_E _gain, ADS1256_DRATE_E _drate);
static void ADS1256_DelayDATA(void);
static uint8_t ADS1256_Recive8Bit(void);
static void ADS1256_WriteReg(uint8_t _RegID, uint8_t _RegValue);
static uint8_t ADS1256_ReadReg(uint8_t _RegID);
static void ADS1256_WriteCmd(uint8_t _cmd);
uint8_t ADS1256_ReadChipID(void);
static void ADS1256_SetChannal(uint8_t _ch);
static void ADS1256_SetDiffChannal(uint8_t _ch);
static void ADS1256_WaitDRDY(void);
static int32_t ADS1256_ReadData(void);

int32_t ADS1256_GetAdc(uint8_t _ch);
void ADS1256_ISR(void);
uint8_t ADS1256_Scan(void);




void  bsp_DelayUS(uint64_t micros)
{
    bcm2835_delayMicroseconds (micros);
}


/*
*********************************************************************************************************
*	name: bsp_InitADS1256
*	function: Configuration of the STM32 GPIO and SPI interface��The connection ADS1256
*	parameter: NULL
*	The return value: NULL
*********************************************************************************************************
*/


void bsp_InitADS1256(void)
{
#ifdef SOFT_SPI
    CS_1();
    SCK_0();
    DI_0();
#endif

//ADS1256_CfgADC(ADS1256_GAIN_1, ADS1256_1000SPS);	/* ����ADC������ ����1:1, ����������� 1KHz */
}




/*
*********************************************************************************************************
*	name: ADS1256_StartScan
*	function: Configuration DRDY PIN for external interrupt is triggered
*	parameter: _ucDiffMode : 0  Single-ended input  8 channel�� 1 Differential input  4 channe
*	The return value: NULL
*********************************************************************************************************
*/
void ADS1256_StartScan(uint8_t _ucScanMode)
{
    g_tADS1256.ScanMode = _ucScanMode;
    /* ��ʼɨ��ǰ, ������������ */
    {
        uint8_t i;

        g_tADS1256.Channel = 0;

        for (i = 0; i < 8; i++)
        {
            g_tADS1256.AdcNow[i] = 0;
        }
    }

}

/*
*********************************************************************************************************
*	name: ADS1256_Send8Bit
*	function: SPI bus to send 8 bit data
*	parameter: _data:  data
*	The return value: NULL
*********************************************************************************************************
*/
static void ADS1256_Send8Bit(uint8_t _data)
{

    bsp_DelayUS(2);
    bcm2835_spi_transfer(_data);
}

/*
*********************************************************************************************************
*	name: ADS1256_CfgADC
*	function: The configuration parameters of ADC, gain and data rate
*	parameter: _gain:gain 1-64
*                      _drate:  data  rate
*	The return value: NULL
*********************************************************************************************************
*/
void ADS1256_CfgADC(ADS1256_GAIN_E _gain, ADS1256_DRATE_E _drate)
{
    g_tADS1256.Gain = _gain;
    g_tADS1256.DataRate = _drate;

    ADS1256_WaitDRDY();

    {
        uint8_t buf[4];		/* Storage ads1256 register configuration parameters */

        /*Status register define
        	Bits 7-4 ID3, ID2, ID1, ID0  Factory Programmed Identification Bits (Read Only)

        	Bit 3 ORDER: Data Output Bit Order
        		0 = Most Significant Bit First (default)
        		1 = Least Significant Bit First
        	Input data  is always shifted in most significant byte and bit first. Output data is always shifted out most significant
        	byte first. The ORDER bit only controls the bit order of the output data within the byte.

        	Bit 2 ACAL : Auto-Calibration
        		0 = Auto-Calibration Disabled (default)
        		1 = Auto-Calibration Enabled
        	When Auto-Calibration is enabled, self-calibration begins at the completion of the WREG command that changes
        	the PGA (bits 0-2 of ADCON register), DR (bits 7-0 in the DRATE register) or BUFEN (bit 1 in the STATUS register)
        	values.

        	Bit 1 BUFEN: Analog Input Buffer Enable
        		0 = Buffer Disabled (default)
        		1 = Buffer Enabled

        	Bit 0 DRDY :  Data Ready (Read Only)
        		This bit duplicates the state of the DRDY pin.

        	ACAL=1  enable  calibration
        */
        buf[0] = (0 << 3) | (1 << 2) | (1 << 1);   // enable the internal buffer
        // [Mark] turn off internal buffer to lower impedance for better noise I hope
        //buf[0] = (0 << 3) | (1 << 2) | (0 << 1);  // The internal buffer is prohibited

        //ADS1256_WriteReg(REG_STATUS, (0 << 3) | (1 << 2) | (1 << 1));

        buf[1] = 0x08;

        /*	ADCON: A/D Control Register (Address 02h)
        	Bit 7 Reserved, always 0 (Read Only)
        	Bits 6-5 CLK1, CLK0 : D0/CLKOUT Clock Out Rate Setting
        		00 = Clock Out OFF
        		01 = Clock Out Frequency = fCLKIN (default)
        		10 = Clock Out Frequency = fCLKIN/2
        		11 = Clock Out Frequency = fCLKIN/4
        		When not using CLKOUT, it is recommended that it be turned off. These bits can only be reset using the RESET pin.

        	Bits 4-3 SDCS1, SCDS0: Sensor Detect Current Sources
        		00 = Sensor Detect OFF (default)
        		01 = Sensor Detect Current = 0.5 �� A
        		10 = Sensor Detect Current = 2 �� A
        		11 = Sensor Detect Current = 10�� A
        		The Sensor Detect Current Sources can be activated to verify  the integrity of an external sensor supplying a signal to the
        		ADS1255/6. A shorted sensor produces a very small signal while an open-circuit sensor produces a very large signal.

        	Bits 2-0 PGA2, PGA1, PGA0: Programmable Gain Amplifier Setting
        		000 = 1 (default)
        		001 = 2
        		010 = 4
        		011 = 8
        		100 = 16
        		101 = 32
        		110 = 64
        		111 = 64
        */
        buf[2] = (0 << 5) | (0 << 3) | (_gain << 0);
        //ADS1256_WriteReg(REG_ADCON, (0 << 5) | (0 << 2) | (GAIN_1 << 1));	/*choose 1: gain 1 ;input 5V/
        buf[3] = s_tabDataRate[_drate];	// DRATE_10SPS;

        CS_0();	/* SPIƬѡ = 0 */
        ADS1256_Send8Bit(CMD_WREG | 0);	/* Write command register, send the register address */
        ADS1256_Send8Bit(0x03);			/* Register number 4,Initialize the number  -1*/

        ADS1256_Send8Bit(buf[0]);	/* Set the status register */
        ADS1256_Send8Bit(buf[1]);	/* Set the input channel parameters */
        ADS1256_Send8Bit(buf[2]);	/* Set the ADCON control register,gain */
        ADS1256_Send8Bit(buf[3]);	/* Set the output rate */

        CS_1();	/* SPI  cs = 1 */
    }

    bsp_DelayUS(50);
}


/*
*********************************************************************************************************
*	name: ADS1256_DelayDATA
*	function: delay
*	parameter: NULL
*	The return value: NULL
*********************************************************************************************************
*/
static void ADS1256_DelayDATA(void)
{
    /*
    	Delay from last SCLK edge for DIN to first SCLK rising edge for DOUT: RDATA, RDATAC,RREG Commands
    	min  50   CLK = 50 * 0.13uS = 6.5uS
    */
    bsp_DelayUS(7);	/* The minimum time delay 6.5us */
}




/*
*********************************************************************************************************
*	name: ADS1256_Recive8Bit
*	function: SPI bus receive function
*	parameter: NULL
*	The return value: NULL
*********************************************************************************************************
*/
static uint8_t ADS1256_Recive8Bit(void)
{
    uint8_t read = 0;
    read = bcm2835_spi_transfer(0xff);
    return read;
}

/*
*********************************************************************************************************
*	name: ADS1256_WriteReg
*	function: Write the corresponding register
*	parameter: _RegID: register  ID
*			 _RegValue: register Value
*	The return value: NULL
*********************************************************************************************************
*/
static void ADS1256_WriteReg(uint8_t _RegID, uint8_t _RegValue)
{
    CS_0();	/* SPI  cs  = 0 */
    ADS1256_Send8Bit(CMD_WREG | _RegID);	/*Write command register */
    ADS1256_Send8Bit(0x00);		/*Write the register number */

    ADS1256_Send8Bit(_RegValue);	/*send register value */
    CS_1();	/* SPI   cs = 1 */
}

/*
*********************************************************************************************************
*	name: ADS1256_ReadReg
*	function: Read  the corresponding register
*	parameter: _RegID: register  ID
*	The return value: read register value
*********************************************************************************************************
*/
static uint8_t ADS1256_ReadReg(uint8_t _RegID)
{
    uint8_t read;

    CS_0();	/* SPI  cs  = 0 */
    ADS1256_Send8Bit(CMD_RREG | _RegID);	/* Write command register */
    ADS1256_Send8Bit(0x00);	/* Write the register number */

    ADS1256_DelayDATA();	/*delay time */

    read = ADS1256_Recive8Bit();	/* Read the register values */
    CS_1();	/* SPI   cs  = 1 */

    return read;
}

/*
*********************************************************************************************************
*	name: ADS1256_WriteCmd
*	function: Sending a single byte order
*	parameter: _cmd : command
*	The return value: NULL
*********************************************************************************************************
*/
static void ADS1256_WriteCmd(uint8_t _cmd)
{
    CS_0();	/* SPI   cs = 0 */
    ADS1256_Send8Bit(_cmd);
    CS_1();	/* SPI  cs  = 1 */
}

/*
*********************************************************************************************************
*	name: ADS1256_ReadChipID
*	function: Read the chip ID
*	parameter: _cmd : NULL
*	The return value: four high status register
*********************************************************************************************************
*/
uint8_t ADS1256_ReadChipID(void)
{
    uint8_t id;

    ADS1256_WaitDRDY();
    id = ADS1256_ReadReg(REG_STATUS);
    return (id >> 4);
}

/*
*********************************************************************************************************
*	name: ADS1256_SetChannal
*	function: Configuration channel number
*	parameter:  _ch:  channel number  0--7
*	The return value: NULL
*********************************************************************************************************
*/
static void ADS1256_SetChannal(uint8_t _ch)
{
    /*
    Bits 7-4 PSEL3, PSEL2, PSEL1, PSEL0: Positive Input Channel (AINP) Select
    	0000 = AIN0 (default)
    	0001 = AIN1
    	0010 = AIN2 (ADS1256 only)
    	0011 = AIN3 (ADS1256 only)
    	0100 = AIN4 (ADS1256 only)
    	0101 = AIN5 (ADS1256 only)
    	0110 = AIN6 (ADS1256 only)
    	0111 = AIN7 (ADS1256 only)
    	1xxx = AINCOM (when PSEL3 = 1, PSEL2, PSEL1, PSEL0 are ��don��t care��)

    	NOTE: When using an ADS1255 make sure to only select the available inputs.

    Bits 3-0 NSEL3, NSEL2, NSEL1, NSEL0: Negative Input Channel (AINN)Select
    	0000 = AIN0
    	0001 = AIN1 (default)
    	0010 = AIN2 (ADS1256 only)
    	0011 = AIN3 (ADS1256 only)
    	0100 = AIN4 (ADS1256 only)
    	0101 = AIN5 (ADS1256 only)
    	0110 = AIN6 (ADS1256 only)
    	0111 = AIN7 (ADS1256 only)
    	1xxx = AINCOM (when NSEL3 = 1, NSEL2, NSEL1, NSEL0 are ��don��t care��)
    */
    if (_ch > 7)
    {
        return;
    }
    ADS1256_WriteReg(REG_MUX, (_ch << 4) | (1 << 3));	/* Bit3 = 1, AINN connection AINCOM */
}

/*
*********************************************************************************************************
*	name: ADS1256_SetDiffChannal
*	function: The configuration difference channel
*	parameter:  _ch:  channel number  0--3
*	The return value:  four high status register
*********************************************************************************************************
*/
static void ADS1256_SetDiffChannal(uint8_t _ch)
{
    /*
    Bits 7-4 PSEL3, PSEL2, PSEL1, PSEL0: Positive Input Channel (AINP) Select
    	0000 = AIN0 (default)
    	0001 = AIN1
    	0010 = AIN2 (ADS1256 only)
    	0011 = AIN3 (ADS1256 only)
    	0100 = AIN4 (ADS1256 only)
    	0101 = AIN5 (ADS1256 only)
    	0110 = AIN6 (ADS1256 only)
    	0111 = AIN7 (ADS1256 only)
    	1xxx = AINCOM (when PSEL3 = 1, PSEL2, PSEL1, PSEL0 are ��don��t care��)

    	NOTE: When using an ADS1255 make sure to only select the available inputs.

    Bits 3-0 NSEL3, NSEL2, NSEL1, NSEL0: Negative Input Channel (AINN)Select
    	0000 = AIN0
    	0001 = AIN1 (default)
    	0010 = AIN2 (ADS1256 only)
    	0011 = AIN3 (ADS1256 only)
    	0100 = AIN4 (ADS1256 only)
    	0101 = AIN5 (ADS1256 only)
    	0110 = AIN6 (ADS1256 only)
    	0111 = AIN7 (ADS1256 only)
    	1xxx = AINCOM (when NSEL3 = 1, NSEL2, NSEL1, NSEL0 are ��don��t care��)
    */
    if (_ch == 0)
    {
        ADS1256_WriteReg(REG_MUX, (0 << 4) | 1);	/* DiffChannal  AIN0�� AIN1 */
    }
    else if (_ch == 1)
    {
        ADS1256_WriteReg(REG_MUX, (2 << 4) | 3);	/*DiffChannal   AIN2�� AIN3 */
    }
    else if (_ch == 2)
    {
        ADS1256_WriteReg(REG_MUX, (4 << 4) | 5);	/*DiffChannal    AIN4�� AIN5 */
    }
    else if (_ch == 3)
    {
        ADS1256_WriteReg(REG_MUX, (6 << 4) | 7);	/*DiffChannal   AIN6�� AIN7 */
    }
}

/*
*********************************************************************************************************
*	name: ADS1256_WaitDRDY
*	function: delay time  wait for automatic calibration
*	parameter:  NULL
*	The return value:  NULL
*********************************************************************************************************
*/
static void ADS1256_WaitDRDY(void)
{
    uint32_t i;

    for (i = 0; i < 400000; i++)
    {
        if (DRDY_IS_LOW())
        {
            break;
        }
    }
    if (i >= 400000)
    {
        printf("ADS1256_WaitDRDY() Time Out ...\r\n");
    }
}

/*
*********************************************************************************************************
*	name: ADS1256_ReadData
*	function: read ADC value
*	parameter: NULL
*	The return value:  NULL
*********************************************************************************************************
*/
static int32_t ADS1256_ReadData(void)
{
    uint32_t read = 0;
    static uint8_t buf[3];

    CS_0();	/* SPI   cs = 0 */

    ADS1256_Send8Bit(CMD_RDATA);	/* read ADC command  */

    ADS1256_DelayDATA();	/*delay time  */

    /*Read the sample results 24bit*/
    buf[0] = ADS1256_Recive8Bit();
    buf[1] = ADS1256_Recive8Bit();
    buf[2] = ADS1256_Recive8Bit();

    read = ((uint32_t)buf[0] << 16) & 0x00FF0000;
    read |= ((uint32_t)buf[1] << 8);  /* Pay attention to It is wrong   read |= (buf[1] << 8) */
    read |= buf[2];

    CS_1();	/* SPIƬѡ = 1 */

    /* Extend a signed number*/
    if (read & 0x800000)
    {
        read |= 0xFF000000;
    }

    return (int32_t)read;
}


/*
*********************************************************************************************************
*	name: ADS1256_GetAdc
*	function: read ADC value
*	parameter:  channel number 0--7
*	The return value:  ADC vaule (signed number)
*********************************************************************************************************
*/
int32_t ADS1256_GetAdc(uint8_t _ch)
{
    int32_t iTemp;

    if (_ch > 7)
    {
        return 0;
    }

    iTemp = g_tADS1256.AdcNow[_ch];

    return iTemp;
}

/*
*********************************************************************************************************
*	name: ADS1256_ISR
*	function: Collection procedures
*	parameter: NULL
*	The return value:  NULL
*********************************************************************************************************
*/
void ADS1256_ISR(void)
{
    if (g_tADS1256.ScanMode == 0)	/*  0  Single-ended input  8 channel�� 1 Differential input  4 channe */
    {

        ADS1256_SetChannal(g_tADS1256.Channel);	/*Switch channel mode */
        bsp_DelayUS(5);

        ADS1256_WriteCmd(CMD_SYNC);
        bsp_DelayUS(5);

        ADS1256_WriteCmd(CMD_WAKEUP);
        bsp_DelayUS(25);

        if (g_tADS1256.Channel == 0)
        {
            g_tADS1256.AdcNow[2] = ADS1256_ReadData();
        }
        else
        {
            g_tADS1256.AdcNow[g_tADS1256.Channel-1] = ADS1256_ReadData();
        }

        if (++g_tADS1256.Channel >= 3)
        {
            g_tADS1256.Channel = 0;
        }
    }
    else	/*DiffChannal*/
    {

        ADS1256_SetDiffChannal(g_tADS1256.Channel);	/* change DiffChannal */
        bsp_DelayUS(5);

        ADS1256_WriteCmd(CMD_SYNC);
        bsp_DelayUS(5);

        ADS1256_WriteCmd(CMD_WAKEUP);
        bsp_DelayUS(25);

        if (g_tADS1256.Channel == 0)
        {
            g_tADS1256.AdcNow[3] = ADS1256_ReadData();
        }
        else
        {
            g_tADS1256.AdcNow[g_tADS1256.Channel-1] = ADS1256_ReadData();
        }

        if (++g_tADS1256.Channel >= 4)
        {
            g_tADS1256.Channel = 0;
        }
    }
}

/*
*********************************************************************************************************
*	name: ADS1256_Scan
*	function:
*	parameter:NULL
*	The return value:  1
*********************************************************************************************************
*/
uint8_t ADS1256_Scan(void)
{
    if (DRDY_IS_LOW())
    {
        ADS1256_ISR();
        return 1;
    }

    return 0;
}
/*
*********************************************************************************************************
*	name: Write_DAC8552
*	function:  DAC send data
*	parameter: channel : output channel number
*			   data : output DAC value
*	The return value:  NULL
*********************************************************************************************************
*/
void Write_DAC8552(uint8_t channel, uint16_t Data)
{
    uint8_t i;

    CS_1() ;
    CS_0() ;
    bcm2835_spi_transfer(channel);
    bcm2835_spi_transfer((Data>>8));
    bcm2835_spi_transfer((Data&0xff));
    CS_1() ;
}
/*
*********************************************************************************************************
*	name: Voltage_Convert
*	function:  Voltage value conversion function
*	parameter: Vref : The reference voltage 3.3V or 5V
*			   voltage : output DAC value
*	The return value:  NULL
*********************************************************************************************************
*/
uint16_t Voltage_Convert(float Vref, float voltage)
{
    uint16_t _D_;
    _D_ = (uint16_t)(65536 * voltage / Vref);

    return _D_;
}


/*
*********************************************************************************************************
*	name: main
*	function:
*	parameter: NULL
*	The return value:  NULL
*********************************************************************************************************
*/

int  main()
{
    uint8_t id;
    int32_t adc[8];
    int32_t adc_local;
    int32_t volt[8];
    int32_t current[8];
    int32_t combined = 0;
    uint8_t i;
    uint8_t ch_num;
    int32_t iTemp;
    uint8_t buf[3];
    if (!bcm2835_init())
        return 1;

    bcm2835_spi_begin();
    bcm2835_spi_setBitOrder(BCM2835_SPI_BIT_ORDER_MSBFIRST);   //default
    bcm2835_spi_setDataMode(BCM2835_SPI_MODE1);                //default
    bcm2835_spi_setClockDivider(BCM2835_SPI_CLOCK_DIVIDER_256);//default

    bcm2835_gpio_fsel(SPICS, BCM2835_GPIO_FSEL_OUTP);//
    bcm2835_gpio_write(SPICS, HIGH);
    bcm2835_gpio_fsel(DRDY, BCM2835_GPIO_FSEL_INPT);
    bcm2835_gpio_set_pud(DRDY, BCM2835_GPIO_PUD_UP);


    id = ADS1256_ReadChipID();
    printf("\r\n");
    printf("ID=\r\n");
    if (id != 3) {
        printf("Error, ASD1256 Chip ID = 0x%d\r\n", (int)id);
    } else {
        printf("Ok, ASD1256 Chip ID = 0x%d\r\n", (int)id);
    }

    RST_1();
    bsp_DelayUS(10000);
    RST_0();
    while(!DRDY_IS_LOW());

    // [Mark] Gain 4 to get 1.25V full scale (2**23-1)
    // 3750 / 3 = 1250 sps potential
    ADS1256_CfgADC(ADS1256_GAIN_4, ADS1256_3750SPS);

    ADS1256_WriteCmd(CMD_SELFOCAL);
    while(!DRDY_IS_LOW());

    ADS1256_StartScan(0);
    ch_num = 3;

    uint8_t ch_index = 0;

    int32_t lastTime = time(NULL);
    int32_t cnt = 0;
    uint8_t log_interval = 1;

    char file_name[128];
    char file_name_cal[128];
    FILE *fp;
    FILE *fp_cal;

    sprintf(file_name_cal, "calibration.txt");
    fp = fopen(file_name_cal, "r");

    bool cal = 0;
    if ((fp_cal = fopen(file_name_cal,"r"))==NULL) {
        cal = 1;
        printf("calibration file not found, running calibration\r\n");
    }
    else
    {
        printf("calibration file found\r\n");
        fclose(fp_cal);
    }

    int32_t cal_done[3] = {0, 0, 0};
    int32_t buffer[3] = {0, 0, 0};
    int64_t cal_value[3] = {0, 0, 0};
    int32_t avg_current = 0;

    
    if (!cal) {
        sprintf(file_name, "/home/pi/lorawan-conformance-testbench/tmp/power/%d.bin", time(NULL)/log_interval);
        fp = fopen(file_name, "wb");
        
        fp_cal = fopen(file_name_cal, "r");
        fscanf(fp_cal, "%d", cal_done);
        fscanf(fp_cal, "%d", cal_done+1);
        fscanf(fp_cal, "%d", cal_done+2);
        fclose(fp_cal);
    }


    while(1) {
        for (ch_index = 0; ch_index < 3; ch_index++) {

            while(!DRDY_IS_LOW());

            ADS1256_SetChannal(ch_index);
            ADS1256_WriteCmd(CMD_SYNC);
            ADS1256_WriteCmd(CMD_WAKEUP);

            // 0 -- 1 ohm, 2 -- 0.1 ohm, 1 -- 0.01 ohm
            volt[ch_index] = ADS1256_ReadData();
            // Step 1:  We should have a positive voltage.  Throw away lower 4 bits of noise
            volt[ch_index] &= ~ (int)((1 << 4) - 1);

            bsp_DelayUS(200);
        }

        //printf("Volts (ADC minus Noise): %ld, %ld, %ld.\n", volt[0], volt[2], volt[1]);

        // [Mark] New idea is to calibrate on the voltages and filter out glitches in the voltages

        // Step 2: If we are calibrating let's create an average of our noise-free voltages
        if (cal) {
            cal_value[0] += volt[0];
            cal_value[1] += volt[1];
            cal_value[2] += volt[2];
            cnt++;

            if (cnt == 16384)
            {
                printf("calibration finished\r\n");

                sprintf(file_name, "calibration.txt");
                fp_cal = fopen(file_name, "w");
                fprintf(fp_cal, "%lld\n", cal_value[0]/cnt);
                fprintf(fp_cal, "%lld\n", cal_value[1]/cnt);
                fprintf(fp_cal, "%lld\n", cal_value[2]/cnt);
                fclose(fp_cal);

                sprintf(file_name, "/home/pi/lorawan-conformance-testbench/tmp/power/%d.bin", time(NULL)/log_interval);
                fp = fopen(file_name, "wb");

                fp_cal = fopen(file_name_cal, "r");
                fscanf(fp_cal, "%d", cal_done);
                fscanf(fp_cal, "%d", cal_done+1);
                fscanf(fp_cal, "%d", cal_done+2);
                fclose(fp_cal);

                cal = 0;
            }
            continue; // [Mark] force next iteration of while loop if in cal
        }

        // [Mark] if we got here, we aren't in calibration anymore!

        //printf("Calibrations: %ld, %ld, %ld.\n", cal_done[0], cal_done[2], cal_done[1]);

        // Step 3: Remove offset and scale voltage removing the gains and aajusting for full scale
        volt[0] = max(volt[0] - cal_done[0], 0) * 100 / 167 / 4; // [Mark] 167 comes from 2 * max of 8388607/100000
        volt[2] = max(volt[2] - cal_done[2], 0) * 100 / 167 / 4; //        this is compensating for the amp gain of 200
        volt[1] = max(volt[1] - cal_done[1], 0) * 100 / 167 / 4;

        //printf("Volts (scaled): %ld, %ld, %ld.\n", volt[0], volt[2], volt[1]);

        // Glitch filter just stuffs a fake value from adjacent channel, scaled appropriately
        // Step 4:  volt[1] > volt[2] > volt[0] or there's trouble!
        //          also consider valid range of volt 0 since it saturates at 4.5/5 * 1.25 V
        //          which is around 7.5 million
        if (volt[0] >= volt[2]) volt[0] = volt[2] / 10;
        if ((volt[2] >= volt[1]) && (volt[1] < 7500000)) volt[2] = volt[1] / 10;
        if ((volt[1] < volt[2]) || (volt[1] > 7500000)) volt[1] = volt[2] * 10;

        //printf("Volts (no glitch): %ld, %ld, %ld.\n", volt[0], volt[2], volt[1]);

        // Step 5: Convert our voltages to the equivalent current
        //          based on the order of the resistors
        current[2] = volt[0] * 500; // flipped the 500 and 5 multipliers from the original!
        current[1] = volt[2] * 50;
        current[0] = volt[1] * 5;

        //printf("Currents (normalized): %ld, %ld, %ld.\n", current[0], current[1], current[2]);



        // Step 6 (if required): get the currents into shape for recording
        // the CTB software expects the current to be an integer that needs to be divided by 1,000,000.0 to become a float

        //printf("Currents: %ld, %ld, %ld.\n", current[0], current[1], current[2]);

        // Step 7: Choose the best current for our sample to record
        //          if we have low or high current measurement choose the appropriate one directly
        //          because the other values will be suspect
        if (current[0] < 100000) avg_current = current[0]; // really low current (0.1 mA or 100 uA)

        else if (current[2] > 10000000) avg_current = current[2];  // relatively high current (10mA)

        else {
        // otherwise: choose the average of the two closest numbers as our sample
            buffer[0] = abs( current[0] - current[1] );
            buffer[1] = abs( current[0] - current[2] );
            buffer[2] = abs( current[1] - current[2] );
            if (buffer[0] <= buffer[1] && buffer[0] <= buffer[2]) {
                avg_current = (current[0] + current[1]) / 2;
                }
            else if (buffer[1] <= buffer[0] && buffer[1] <= buffer[2]) {
                avg_current = (current[0] + current[2]) / 2;
                }
            else avg_current = (current[1] + current[2]) / 2;
        }

        //printf("Sample Current: %ld.\n", avg_current);

        // Step 8: write out the sample
        fwrite(&avg_current, 4, 1, fp);
        cnt++;

        // Step 9: write out the file if an interval has elapsed and open a new one
        if (lastTime < time(NULL)/log_interval) {
            printf("Power meter: %ld points saved\n", cnt);
            cnt = 0;
            lastTime = time(NULL)/log_interval;

            fclose(fp);
            sprintf(file_name, "/home/pi/lorawan-conformance-testbench/tmp/power/%d.bin", lastTime);
            fp = fopen(file_name, "wb");
        }
    }

    bcm2835_spi_end();
    bcm2835_close();

    return 0;
}