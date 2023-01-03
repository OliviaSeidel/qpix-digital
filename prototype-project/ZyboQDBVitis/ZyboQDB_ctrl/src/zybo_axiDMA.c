#include "xaxidma.h"
#include "xparameters.h"
#include "xdebug.h"

// interuption things
#include "xil_exception.h"
#include "xil_cache.h"
#include "xparameters.h"
#include "xscugic.h"
#define INTC_DEVICE_ID		XPAR_SCUGIC_SINGLE_DEVICE_ID
static XScuGic zyboIntcControl;

// xpars base addr
#define dma_baseaddr XPAR_AXI_DMA_BASEADDR
#define DMA_DEV_ID	XPAR_AXIDMA_0_DEVICE_ID
#define RX_INTR_ID	61 // interrupt defined on pin within board design

// UDP interface to send data
void udp_packet_send(u16 size_t);

// example_simple_test
int AxiDMASelfTestExample(u16 DeviceId);
extern XAxiDma AxiDma;

// example simple_poll
int XAxiDma_SimplePollExample(u16 DeviceId);
XAxiDma_Config *ZyboDmaCfgPtr;

/* BUFFER MANAGEMENT */
#define TX_BUFFER_BASE	0x00000000
#define ZYBO_LENGTH 0x00003fff // max length is 26 bits?
#define ZYBO_CTRL_INIT 0x00011003 // enable on complete, running, and other things in docs
#define ZYBO_DEST_BUFF 0x00000123
u32 data_buf[ZYBO_LENGTH];

/* REGISTER FUNCTIONS */
// create dma register read function for finding the current dest pointer
u32 getDestReg(XAxiDma* pDma)
{
	u32 destReg = XAXIDMA_RX_OFFSET + XAXIDMA_RX_TDESC0_OFFSET;
	u32 regVal = XAxiDma_ReadReg(pDma->RegBase, destReg);
	return regVal;
}

void setDestReg(XAxiDma* pDma)
{
	u32 destReg = XAXIDMA_RX_OFFSET + XAXIDMA_RX_TDESC0_OFFSET;
	XAxiDma_WriteReg(pDma->RegBase, destReg, ZYBO_DEST_BUFF);
}

u32 getCtrlReg(XAxiDma* pDma)
{
	u32 destReg = XAXIDMA_RX_OFFSET + XAXIDMA_CR_OFFSET;
	u32 regVal = XAxiDma_ReadReg(pDma->RegBase, destReg);
	return regVal;
}

void setCtrlReg(XAxiDma* pDma)
{
	u32 destReg = XAXIDMA_RX_OFFSET + XAXIDMA_CR_OFFSET;
	XAxiDma_WriteReg(pDma->RegBase, destReg, ZYBO_CTRL_INIT);
}

u32 getStatusReg(XAxiDma* pDma)
{
	u32 destReg = XAXIDMA_RX_OFFSET + XAXIDMA_SR_OFFSET;
	u32 regVal = XAxiDma_ReadReg(pDma->RegBase, destReg);
	return regVal;
}

u32 getDestDirReg(XAxiDma* pDma)
{
	u32 destReg = XAXIDMA_RX_OFFSET + XAXIDMA_DESTADDR_OFFSET;
	u32 regVal = XAxiDma_ReadReg(pDma->RegBase, destReg);
	return regVal;
}

// make sure that the DMA knows how much depth it can store
void setLenReg(XAxiDma* pDma)
{
	u32 destReg = XAXIDMA_RX_OFFSET + XAXIDMA_BUFFLEN_OFFSET;
	XAxiDma_WriteReg(pDma->RegBase, destReg, ZYBO_LENGTH);
}
// verify that we set the register that we wanted to
u32 getLenReg(XAxiDma* pDma)
{
	u32 destReg = XAXIDMA_RX_OFFSET + XAXIDMA_BUFFLEN_OFFSET;
	u32 regVal = XAxiDma_ReadReg(pDma->RegBase, destReg);
	return regVal;
}

// verify the board is doing what we think
int test_zybo_dma()
{

	/* Run the poll example for simple transfer */
	int Status;
	Status = AxiDMASelfTestExample(DMA_DEV_ID);

	if (Status != XST_SUCCESS) {
		xil_printf("AxiDMASelfTest Example Failed\r\n");
		return XST_FAILURE;
	}

	xil_printf("Successfully ran AxiDMASelfTest Example\r\n");
	return XST_SUCCESS;
}

void dump_zybo_config(XAxiDma*);


int ZyboSetupIntrSystem(XScuGic *IntcInstancePtr, XAxiDma *InstancePtr,
			u32 IntrId);
#define INTC_HANDLER	XScuGic_InterruptHandler
volatile int TxDone;
volatile int RxDone;
volatile int Error;

// setup the board the way we want it to be-> This should allow read_udp to ping and build
// the required packets to send
int configure_zybo_dma()
{
	int Status;
//	u8 *TxBufferPtr;
//	TxBufferPtr = (u8 *)TX_BUFFER_BASE;
	XAxiDma* pDma;
	pDma = &AxiDma;

	/* Initialize the XAxiDma device.*/
	ZyboDmaCfgPtr = XAxiDma_LookupConfig(DMA_DEV_ID);
	if (!ZyboDmaCfgPtr) {
		xil_printf("No config found for %d\r\n", DMA_DEV_ID);
		return XST_FAILURE;
	}

	Status = XAxiDma_CfgInitialize(&AxiDma, ZyboDmaCfgPtr);
	if (Status != XST_SUCCESS) {
		xil_printf("Initialization failed %d\r\n", Status);
		return XST_FAILURE;
	}

	// make sure that the config registers get set properly
	setCtrlReg(&AxiDma);
	setDestReg(&AxiDma);
	setLenReg(&AxiDma);

	dump_zybo_config(pDma);

	// configure the interrupt and the call back here, this is the loop in to sending UDP packets
	Status = ZyboSetupIntrSystem(&zyboIntcControl, &AxiDma, RX_INTR_ID);

	xil_printf("successfully configured ZYBO DMA \r\n");
	return XST_SUCCESS;
}

void dump_zybo_config(XAxiDma* pDma)
{
	UINTPTR RegBase = pDma->RegBase;
	xil_printf("Dump registers %p:\r\n", (void *)RegBase);

	// get the other registers we care about
	u32 destReg = getDestReg(pDma);
	u32 ctrlReg = getCtrlReg(pDma);
	u32 statReg = getStatusReg(pDma);
	u32 destDirReg = getDestDirReg(pDma);
	u32 lenReg = getLenReg(pDma);

	xil_printf("dest REG: %08x\r\n", destReg);
	xil_printf("ctrl REG: %08x\r\n", ctrlReg);
	xil_printf("stat REG: %08x\r\n", statReg);
	xil_printf("dir REG: %08x\r\n", destDirReg);
	xil_printf("len REG: %08x\r\n", lenReg);
}

static void RxIntrHandler(void *Callback);
int ZyboSetupIntrSystem(XScuGic *IntcInstancePtr, XAxiDma *InstancePtr,
		u32 IntrId)
{
	int Status;
	Status = 0;

	XScuGic_Config *IntcConfig;

	/*
	 * Initialize the interrupt controller driver so that it is ready to
	 * use.
	 */
	IntcConfig = XScuGic_LookupConfig(INTC_DEVICE_ID);
	if (NULL == IntcConfig) {
		return XST_FAILURE;
	}

	Status = XScuGic_CfgInitialize(IntcInstancePtr, IntcConfig,
					IntcConfig->CpuBaseAddress);
	if (Status != XST_SUCCESS) {
		return XST_FAILURE;
	}

	/* connect the Handler */
	Status = XScuGic_Connect(IntcInstancePtr, IntrId,
				(Xil_InterruptHandler)RxIntrHandler,
				InstancePtr);
	if (Status != XST_SUCCESS) {
		return Status;
	}

	/* Disable all interrupts before setup */
	XAxiDma_IntrDisable(InstancePtr, XAXIDMA_IRQ_ALL_MASK,
				XAXIDMA_DEVICE_TO_DMA);

	/* Enable all interrupts */
	XAxiDma_IntrEnable(InstancePtr, XAXIDMA_IRQ_ALL_MASK,
							XAXIDMA_DMA_TO_DEVICE);

	XScuGic_Enable(IntcInstancePtr, IntrId);

	/* Enable interrupts from the hardware */
	Xil_ExceptionInit();
	Xil_ExceptionRegisterHandler(XIL_EXCEPTION_ID_INT,
			(Xil_ExceptionHandler)INTC_HANDLER,
			(void *)IntcInstancePtr);

	Xil_ExceptionEnable();

	return Status;
}

// taken from Xilinx src
/*****************************************************************************/
/*
*
* This is the DMA RX interrupt handler function
*
* It gets the interrupt status from the hardware, acknowledges it, and if any
* error happens, it resets the hardware. Otherwise, if a completion interrupt
* is present, then it sets the RxDone flag.
*
* @param	Callback is a pointer to RX channel of the DMA engine.
*
* @return	None.
*
* @note		None.
*
******************************************************************************/
static void RxIntrHandler(void *Callback)
{
	u32 IrqStatus;
	XAxiDma *AxiDmaInst = (XAxiDma *)Callback;
	u32 *DataBufPtr;

	/* Read pending interrupts */
	IrqStatus = XAxiDma_IntrGetIrq(AxiDmaInst, XAXIDMA_DEVICE_TO_DMA);

	/* Acknowledge pending interrupts */
	XAxiDma_IntrAckIrq(AxiDmaInst, IrqStatus, XAXIDMA_DEVICE_TO_DMA);

	/*
	 * If no interrupt is asserted, we do not do anything
	 */
	if (!(IrqStatus & XAXIDMA_IRQ_ALL_MASK)) {
		return;
	}

	/*
	 * If error interrupt is asserted, raise error flag, reset the
	 * hardware to recover from the error, and return with no further
	 * processing.
	 */
	if ((IrqStatus & XAXIDMA_IRQ_ERROR_MASK)) {

		Error = 1;

		/* Reset could fail and hang
		 * NEED a way to handle this or do not call it??
		 */
		XAxiDma_Reset(AxiDmaInst);

		return;
	}

	/*
	 * If completion interrupt is asserted, then set RxDone flag
	 */
	if ((IrqStatus & XAXIDMA_IRQ_IOC_MASK)) {
		dump_zybo_config(AxiDmaInst);
		u32 Length = getLenReg(AxiDmaInst);
		u32 Dest = getDestReg(AxiDmaInst);
		DataBufPtr = (u32 *)Dest;
		Xil_DCacheFlushRange((UINTPTR)Dest, Length);

		/* read the buffers here, then re-enable */
		int i;
		for(i = 0; i < Length/4; ++i){
			u32 reg = Dest + i;
			u32 data = *(DataBufPtr + i);
			memcpy(&data_buf[i], DataBufPtr+i, 4);
//			xil_printf("REG: %08x, DATA: %08x\r\n", reg, data);
		}

//		xil_printf("sending UDP data! \r\n");
		udp_packet_send(Length);

		/*Re-arm for more data!*/
		setCtrlReg(AxiDmaInst);
		setDestReg(AxiDmaInst);
		setLenReg(AxiDmaInst);
		RxDone = 1;
	}
}
