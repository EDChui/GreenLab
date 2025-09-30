# Set up virtual environment
python3 -m venv venv
source venv/bin/activate

# Install required packages
pip install -r experiment-runner/requirements.txt
pip install -r orc/requirements.txt

# Copy environment variable template
cp .env.template .env