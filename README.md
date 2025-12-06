# tradem-client

Python client for the Tradem platform API.

Has been adapted from https://github.com/The-Brawl/the-brawl-client-api by Mateusz Bajorek.

## Project Structure

- `src/`: Source code
    - `tradem_client.py`: Main client class
    - `models.py`: Data models
    - `example.py`: Example usage script
- `requirements.txt`: Python dependencies
- `server_certificate.pem`: SSL certificate bundle

## Configuration

1.  Create a `.env` file in the root directory with your credentials:

```env
EMAIL=your_email@example.com
PASSWORD=your_password
```

## Getting started

1.  Clone the repository.

2.  Create a virtual environment:
```bash
python3 -m venv .venv
source .venv/bin/activate
```
3.  Install dependencies:
```bash
pip install -r requirements.txt
```

4. Run the example from the `src` directory:

```bash
cd src
python3 example.py
```

## Testing

```bash
PYTHONPATH=src python3 -m unittest discover tests
```
