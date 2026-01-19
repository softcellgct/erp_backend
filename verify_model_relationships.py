import sys
import os

# Add src to path
sys.path.append(os.path.join(os.getcwd(), 'src'))

from sqlalchemy import create_engine
from sqlalchemy.orm import configure_mappers
from common.models.billing.financial_year import FinancialYear
from common.models.master.academic_year import AcademicYear

try:
    print("Configuring mappers...")
    configure_mappers()
    print("Mappers configured successfully.")
    print(f"FinancialYear.academic_year: {FinancialYear.academic_year}")
    print(f"AcademicYear.financial_years: {AcademicYear.financial_years}")
except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)
