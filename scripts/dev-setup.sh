#!/bin/bash
# Development setup script

echo "🛠️ Setting up development environment..."

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies including dev tools
pip install -r requirements.txt
pip install -e .[dev]

# Create pre-commit hook
cat > .git/hooks/pre-commit << 'HOOK'
#!/bin/bash
echo "Running pre-commit checks..."
black src/ --check
flake8 src/
pytest tests/ -q
HOOK

chmod +x .git/hooks/pre-commit

echo "✅ Development environment ready!"
echo "Activate with: source venv/bin/activate"
