#!/usr/bin/env python
"""
Database initialization script for CheckTime.
This script creates the tables needed for the application.
"""

import logging
from datetime import datetime, timedelta
from checktime.shared.config import get_admin_password, get_database_url, get_telegram_chat_id
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from flask import Flask

from checktime.shared.db import db
from checktime.shared.models import User, Holiday, SchedulePeriod, DaySchedule
from checktime.shared.repository import user_repository, holiday_repository
from checktime.shared.repository import schedule_period_repository, day_schedule_repository
from checktime.shared.services.user_manager import UserManager

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

def init_db():
    """Initialize the database with tables and base data."""
    logger.info("Initializing database...")
    
    # Create a temporary Flask app to use its context
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = get_database_url()
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    
    # Initialize the database with the Flask app
    with app.app_context():
        # Create tables
        db.init_app(app)
        db.create_all()
        logger.info("Tables created successfully")
        
        # Check if admin user exists
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            admin = User(
                username='admin',
                email='admin@example.com',
                is_admin=True,
            )
            admin.set_password(get_admin_password())
            
            # Set Telegram chat ID from environment variable
            telegram_chat_id = get_telegram_chat_id()
            if telegram_chat_id:
                admin.telegram_chat_id = telegram_chat_id
                admin.telegram_notifications_enabled = True
                logger.info(f"Admin user created with Telegram chat ID: {telegram_chat_id}")
            else:
                logger.info("Admin user created without Telegram chat ID (not set in environment)")
                
            db.session.add(admin)
            db.session.commit()
            logger.info("Admin user created")
        
        # Add some sample holidays
        if Holiday.query.count() == 0:
            holidays = [
                Holiday(date=datetime(2025, 1, 1).date(), description="New Year's Day", user_id=admin.id),
                Holiday(date=datetime(2025, 12, 25).date(), description="Christmas Day", user_id=admin.id),
            ]
            for holiday in holidays:
                db.session.add(holiday)
            db.session.commit()
            logger.info("Sample holidays added")
        
        # Add a default schedule period
        if SchedulePeriod.query.count() == 0:
            period = SchedulePeriod(
                name="Standard Schedule",
                start_date=datetime(2025, 1, 1).date(),
                end_date=datetime(2025, 12, 31).date(),
                is_active=True,
                user_id=admin.id
            )
            db.session.add(period)
            db.session.flush()  # To get the ID
            
            # Add day schedules
            day_schedules = [
                DaySchedule(period_id=period.id, day_of_week=0, check_in_time="09:00", check_out_time="18:00"),  # Monday
                DaySchedule(period_id=period.id, day_of_week=1, check_in_time="09:00", check_out_time="18:00"),  # Tuesday
                DaySchedule(period_id=period.id, day_of_week=2, check_in_time="09:00", check_out_time="18:00"),  # Wednesday
                DaySchedule(period_id=period.id, day_of_week=3, check_in_time="09:00", check_out_time="18:00"),  # Thursday
                DaySchedule(period_id=period.id, day_of_week=4, check_in_time="09:00", check_out_time="17:00"),  # Friday
            ]
            for day_schedule in day_schedules:
                db.session.add(day_schedule)
                
            db.session.commit()
            logger.info("Default schedule created")
        
    logger.info("Database initialization complete")

def create_admin_user():
    """Create admin user if it doesn't exist."""
    # Initialize UserManager
    user_manager = UserManager()
    
    # Check if admin user exists
    admin = User.query.filter_by(username='admin').first()
    
    if not admin:
        logger.info("Creating admin user")
        
        # Create admin user
        admin = user_repository.create_user(
            username='admin',
            email='admin@example.com',
            password=get_admin_password(),
            is_admin=True
        )
        
        # Set Telegram chat ID from environment variable
        telegram_chat_id = get_telegram_chat_id()
        if telegram_chat_id:
            user_manager.set_telegram_settings(
                user_id=admin.id,
                chat_id=telegram_chat_id,
                enabled=True
            )
            logger.info(f"Set Telegram chat ID for admin user: {telegram_chat_id}")
        else:
            logger.info("No Telegram chat ID set in environment for admin user")

        logger.info("Admin user created successfully")
    else:
        logger.info("Admin user already exists")
    
    return admin

def create_default_holidays(admin_user):
    """Create some default holidays."""
    # Example holidays for the current year
    year = datetime.now().year
    
    holidays = [
        (f"{year}-01-01", "New Year's Day"),
        (f"{year}-12-25", "Christmas Day"),
        (f"{year}-07-04", "Independence Day"),
    ]
    
    for date_str, description in holidays:
        # Convert to datetime.date
        date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
        
        # Check if holiday exists
        existing = holiday_repository.get_by_date(date_obj, admin_user.id)
        
        if not existing:
            logger.info(f"Creating holiday: {date_str} - {description}")
            holiday_repository.create(date_obj, description, admin_user.id)

def create_default_schedule(admin_user):
    """Create a default schedule if none exists."""
    # Get all schedule periods for the admin user
    periods = schedule_period_repository.get_active_periods(admin_user.id)
    
    if not periods:
        logger.info("Creating default schedule period")
        
        # Create schedule period for the current year
        now = datetime.now()
        start_date = datetime(now.year, 1, 1).date()
        end_date = datetime(now.year, 12, 31).date()
        
        # Create schedule period
        period = schedule_period_repository.create_period(
            name="Standard Schedule",
            start_date=start_date,
            end_date=end_date,
            is_active=True,
            user_id=admin_user.id
        )
        
        # Create schedule for each day (Monday to Friday)
        for day in range(5):  # 0 = Monday, 4 = Friday
            day_schedule_repository.create_day_schedule(
                period_id=period.id,
                day_of_week=day,
                check_in_time="09:00",
                check_out_time="18:00"
            )
            
        logger.info("Default schedule created successfully")
    else:
        logger.info("Schedule already exists")

def init_defaults(app: Flask = None):
    """Initialize default data."""
    logger.info("Initializing default data")
    
    # Create admin user and get the reference
    admin_user = create_admin_user()
    
    # Create default holidays
    create_default_holidays(admin_user)
    
    # Create default schedule
    create_default_schedule(admin_user)
    
    logger.info("Default data initialization complete")

if __name__ == "__main__":
    init_db() 