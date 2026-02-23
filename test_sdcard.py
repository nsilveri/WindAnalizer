# Rui Santos & Sara Santos - Random Nerd Tutorials
# Complete project details at https://RandomNerdTutorials.com/raspberry-pi-pico-microsd-card-micropython/
 
from machine import SPI, Pin
import lib.sdcard as sdcard
import os

# Constants
SPI_BUS     = 0
CS_PIN      = 17
SCK_PIN     = 18
MISO_PIN    = 20 #RX_PIN
MOSI_PIN    = 19 #TX_PIN

SD_MOUNT_PATH = '/sd'
FILE_PATH = 'sd/sd_file.txt'

FORMAT_SD = False

try:
    # Init SPI communication
    spi = SPI(SPI_BUS,sck=Pin(SCK_PIN), mosi=Pin(MOSI_PIN), miso=Pin(MISO_PIN))
    cs = Pin(CS_PIN)
    print("SPI communication initialized successfully.")
    sd = sdcard.SDCard(spi, cs)

    if FORMAT_SD:
        # Format the microSD card (this will erase all data on the card)
        print("Formatting microSD card...")
        sd.format_sd()
    else:
        print("microSD card already formatted. Skipping formatting step.")

    # Mount microSD card
    os.mount(sd, SD_MOUNT_PATH)
    # List files on the microSD card
    print(os.listdir(SD_MOUNT_PATH))
    
    # Create new file on the microSD card
    with open(FILE_PATH, "w") as file:
        # Write to the file
        file.write("Testing microSD Card \n")
        
    # Check that the file was created:
    print(os.listdir(SD_MOUNT_PATH))
    
    # Open the file in reading mode
    with open(FILE_PATH, "r") as file:
        # read the file content
        content = file.read()
        print("File content:", content)  
    
except Exception as e:
    print('An error occurred:', e)