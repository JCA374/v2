# Example directory structure and commands

# Create project directory
mkdir yahoo - ticker - tool
cd yahoo - ticker - tool

# Initialize project and install dependencies
npm init - y
npm install papaparse

# Create the script file(copy the code from the first artifact)
touch yahoo - finance - ticker - lookup.js
#(paste the Node.js code here)

# Example input CSV(sample - tickers.csv)
cat > sample - tickers.csv << EOL
Tickersymbol
AAPL
MSFT
GOOGL
AMZN
TSLA
NVDA
META
BRK.B
BABA
ASML
EOL

# Run the script
node yahoo - finance - ticker - lookup.js sample - tickers.csv yahoo - results.csv

# For a CSV with a different column name
cat > nordic - tickers.csv << EOL
Symbol
NOKIA
ERIC - B
NDA - SE
SAND
DANSKE
DNB
SAMPO
NOVO - B
VOLV - B
ATLAS
EOL

# Run with custom column name
node yahoo - finance - ticker - lookup.js nordic - tickers.csv nordic - yahoo.csv Symbol

# View the first few lines of the results
head yahoo - results.csv