from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, current_app, session, g
from flask_login import login_required, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, DateField, BooleanField, SubmitField, SelectField, TimeField, FormField, FieldList
from wtforms.validators import DataRequired, ValidationError
from datetime import datetime, date, timedelta
import logging

from checktime.shared.models.schedule import SchedulePeriod, DaySchedule
from checktime.shared.repository import schedule_period_repository, day_schedule_repository
from checktime.web.translations import get_translation

schedules_bp = Blueprint('schedules', __name__, url_prefix='/schedules')

def get_language():
    """Get the current language from session or default to 'en'"""
    return session.get('lang', 'en')

def flash_message(key, category='success'):
    """Flash a message with proper translation based on current language context"""
    # Get language from Flask g object if available, otherwise from session
    lang = getattr(g, 'language', get_language())
    flash(get_translation(key, lang), category)

def is_ajax_request():
    """Check if a request is an AJAX request."""
    return (
        request.headers.get('X-Requested-With') == 'XMLHttpRequest' or
        request.is_xhr or
        request.headers.get('Content-Type') == 'application/json'
    )

class DayScheduleForm(FlaskForm):
    day_of_week = SelectField('Day', choices=[(0, 'Monday'), (1, 'Tuesday'), (2, 'Wednesday'), 
                                             (3, 'Thursday'), (4, 'Friday'), (5, 'Saturday'), 
                                             (6, 'Sunday')], coerce=int)
    check_in_time = StringField('Check-in Time (HH:MM)', validators=[DataRequired()])
    check_out_time = StringField('Check-out Time (HH:MM)', validators=[DataRequired()])
    
    def __init__(self, *args, **kwargs):
        super(DayScheduleForm, self).__init__(*args, **kwargs)
        # Set translated labels
        lang = get_language()
        self.day_of_week.label.text = get_translation('day', lang)
        self.check_in_time.label.text = get_translation('check_in_time', lang)
        self.check_out_time.label.text = get_translation('check_out_time', lang)
        
        # Translate day choices
        day_translations = [
            ('monday', 'Monday'),
            ('tuesday', 'Tuesday'),
            ('wednesday', 'Wednesday'),
            ('thursday', 'Thursday'),
            ('friday', 'Friday'),
            ('saturday', 'Saturday'),
            ('sunday', 'Sunday')
        ]
        
        # Update choices with translated values
        self.day_of_week.choices = [
            (i, get_translation(day_key, lang)) 
            for i, (day_key, _) in enumerate(day_translations)
        ]

class SchedulePeriodForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired()])
    start_date = DateField('Start Date', format='%Y-%m-%d', validators=[DataRequired()])
    end_date = DateField('End Date', format='%Y-%m-%d', validators=[DataRequired()])
    is_active = BooleanField('Active')
    submit = SubmitField('Save')
    
    def __init__(self, *args, **kwargs):
        super(SchedulePeriodForm, self).__init__(*args, **kwargs)
        # Set translated labels
        lang = get_language()
        self.name.label.text = get_translation('period_name', lang)
        self.start_date.label.text = get_translation('start_date', lang)
        self.end_date.label.text = get_translation('end_date', lang)
        self.is_active.label.text = get_translation('active_period', lang)
        self.submit.label.text = get_translation('btn_save_period', lang)
    
    def validate_end_date(self, field):
        if field.data < self.start_date.data:
            lang = get_language()
            raise ValidationError(get_translation('end_date_after_start', lang))

@schedules_bp.route('/')
@login_required
def index():
    """List all schedule periods."""
    periods = schedule_period_repository.get_all(current_user.id)
    return render_template('schedules/index.html', periods=periods)

@schedules_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add():
    """Add a new schedule period."""
    form = SchedulePeriodForm()
    if form.validate_on_submit():
        # Check for overlapping periods
        if schedule_period_repository.check_overlap(form.start_date.data, form.end_date.data, current_user.id) and form.is_active.data:
            if is_ajax_request():
                return jsonify({
                    'success': False,
                    'message': get_translation('period_overlap_error', get_language())
                }), 409
            else:
                flash_message('period_overlap_error', 'danger')
                return redirect(url_for('schedules.add'))
        
        # Create new period
        period = schedule_period_repository.create_period(
            name=form.name.data,
            start_date=form.start_date.data,
            end_date=form.end_date.data,
            is_active=form.is_active.data,
            user_id=current_user.id
        )
        
        if is_ajax_request():
            return jsonify({
                'success': True,
                'message': get_translation('period_added', get_language()),
                'redirect_url': url_for('schedules.edit_days', period_id=period.id)
            })
        else:
            flash_message('period_added')
            return redirect(url_for('schedules.edit_days', period_id=period.id))
    
    return render_template('schedules/add.html', form=form)

@schedules_bp.route('/edit/<int:period_id>', methods=['GET', 'POST'])
@login_required
def edit(period_id):
    """Edit an existing schedule period."""
    period = schedule_period_repository.get_by_id(period_id, current_user.id)
    if not period:
        if is_ajax_request():
            return jsonify({
                'success': False,
                'message': get_translation('period_not_found', get_language())
            }), 404
        else:
            flash_message('period_not_found', 'danger')
            return redirect(url_for('schedules.index'))
        
    form = SchedulePeriodForm(obj=period)
    # Update the submit button label to reflect an update operation
    lang = get_language()
    form.submit.label.text = get_translation('btn_update_period', lang)
    
    if form.validate_on_submit():
        # Check for overlapping periods
        if schedule_period_repository.check_overlap(form.start_date.data, form.end_date.data, current_user.id, period_id) and form.is_active.data:
            if is_ajax_request():
                return jsonify({
                    'success': False,
                    'message': get_translation('period_overlap_error', get_language())
                }), 409
            else:
                flash_message('period_overlap_error', 'danger')
                return redirect(url_for('schedules.edit', period_id=period_id))
        
        # Update period
        schedule_period_repository.update_period(
            period=period,
            name=form.name.data,
            start_date=form.start_date.data,
            end_date=form.end_date.data,
            is_active=form.is_active.data
        )
        
        if is_ajax_request():
            return jsonify({
                'success': True,
                'message': get_translation('period_updated', get_language()),
                'redirect_url': url_for('schedules.index')
            })
        else:
            flash_message('period_updated')
            return redirect(url_for('schedules.index'))
    
    return render_template('schedules/edit.html', form=form, period=period)

@schedules_bp.route('/delete/<int:period_id>', methods=['POST'])
@login_required
def delete(period_id):
    """Delete a schedule period."""
    period = schedule_period_repository.get_by_id(period_id, current_user.id)
    if not period:
        if is_ajax_request():
            return jsonify({
                'success': False,
                'message': get_translation('period_not_found', get_language())
            }), 404
        else:
            flash_message('period_not_found', 'danger')
            return redirect(url_for('schedules.index'))
    
    schedule_period_repository.delete(period)
    
    if is_ajax_request():
        return jsonify({
            'success': True,
            'message': get_translation('period_deleted', get_language()),
            'redirect_url': url_for('schedules.index')
        })
    else:
        flash_message('period_deleted')
        return redirect(url_for('schedules.index'))

@schedules_bp.route('/period/<int:period_id>/days', methods=['GET', 'POST'])
@login_required
def edit_days(period_id):
    """Edit the daily schedules for a period."""
    period = schedule_period_repository.get_by_id(period_id, current_user.id)
    if not period:
        if is_ajax_request():
            return jsonify({
                'success': False,
                'message': get_translation('period_not_found', get_language())
            }), 404
        else:
            flash_message('period_not_found', 'danger')
            return redirect(url_for('schedules.index'))
    
    if request.method == 'POST':
        # First, delete existing schedules
        day_schedule_repository.delete_all_for_period(period_id)
        
        # Process each day of the week
        for day in range(7):
            if f'day_{day}_enabled' in request.form:
                check_in_time = request.form.get(f'day_{day}_check_in')
                check_out_time = request.form.get(f'day_{day}_check_out')
                
                if check_in_time and check_out_time:
                    day_schedule_repository.create_day_schedule(
                        period_id=period_id,
                        day_of_week=day,
                        check_in_time=check_in_time,
                        check_out_time=check_out_time
                    )
        
        if is_ajax_request():
            return jsonify({
                'success': True,
                'message': get_translation('day_schedules_updated', get_language()),
                'redirect_url': url_for('schedules.index')
            })
        else:
            flash_message('day_schedules_updated')
            return redirect(url_for('schedules.index'))
    
    # Prepare existing schedules for template
    schedules = day_schedule_repository.get_all_by_period(period_id)
    day_schedules = {schedule.day_of_week: schedule for schedule in schedules}
    
    # Get translated day names
    lang = get_language()
    days = [
        get_translation('monday', lang),
        get_translation('tuesday', lang),
        get_translation('wednesday', lang),
        get_translation('thursday', lang),
        get_translation('friday', lang),
        get_translation('saturday', lang),
        get_translation('sunday', lang)
    ]
    
    return render_template(
        'schedules/edit_days.html',
        period=period,
        day_schedules=day_schedules,
        days=days
    )

@schedules_bp.route('/api/add', methods=['POST'])
@login_required
def api_add():
    """API endpoint for adding a new schedule period."""
    try:
        data = request.get_json()
        
        if not data or 'name' not in data or 'start_date' not in data or 'end_date' not in data:
            return jsonify({
                'success': False, 
                'message': get_translation('missing_required_fields', get_language())
            }), 400
            
        # Parse dates
        try:
            start_date = datetime.strptime(data['start_date'], '%Y-%m-%d').date()
            end_date = datetime.strptime(data['end_date'], '%Y-%m-%d').date()
        except ValueError:
            return jsonify({
                'success': False, 
                'message': get_translation('invalid_date_format', get_language())
            }), 400
            
        # Validate end date is after start date
        if end_date < start_date:
            return jsonify({
                'success': False, 
                'message': get_translation('end_date_after_start', get_language())
            }), 400
            
        is_active = data.get('is_active', False)
        
        # Check for overlapping periods
        if schedule_period_repository.check_overlap(start_date, end_date, current_user.id) and is_active:
            return jsonify({
                'success': False, 
                'message': get_translation('period_overlap_error', get_language())
            }), 409
        
        # Create new period
        period = schedule_period_repository.create_period(
            name=data['name'],
            start_date=start_date,
            end_date=end_date,
            is_active=is_active,
            user_id=current_user.id
        )
        
        return jsonify({
            'success': True,
            'message': get_translation('period_added', get_language()),
            'period': {
                'id': period.id,
                'name': period.name,
                'start_date': period.start_date.strftime('%Y-%m-%d'),
                'end_date': period.end_date.strftime('%Y-%m-%d'),
                'is_active': period.is_active
            }
        }), 201
    except Exception as e:
        logging.error(f"Error adding schedule period: {str(e)}")
        return jsonify({
            'success': False, 
            'message': get_translation('error_saving_period', get_language())
        }), 500

@schedules_bp.route('/api/update/<int:period_id>', methods=['PUT'])
@login_required
def api_update(period_id):
    """API endpoint for updating a schedule period."""
    try:
        period = schedule_period_repository.get_by_id(period_id, current_user.id)
        if not period:
            return jsonify({
                'success': False, 
                'message': get_translation('period_not_found', get_language())
            }), 404
            
        data = request.get_json()
        
        if not data or 'name' not in data or 'start_date' not in data or 'end_date' not in data:
            return jsonify({
                'success': False, 
                'message': get_translation('missing_required_fields', get_language())
            }), 400
            
        # Parse dates
        try:
            start_date = datetime.strptime(data['start_date'], '%Y-%m-%d').date()
            end_date = datetime.strptime(data['end_date'], '%Y-%m-%d').date()
        except ValueError:
            return jsonify({
                'success': False, 
                'message': get_translation('invalid_date_format', get_language())
            }), 400
            
        # Validate end date is after start date
        if end_date < start_date:
            return jsonify({
                'success': False, 
                'message': get_translation('end_date_after_start', get_language())
            }), 400
            
        is_active = data.get('is_active', False)
        
        # Check for overlapping periods
        if schedule_period_repository.check_overlap(start_date, end_date, current_user.id, period_id) and is_active:
            return jsonify({
                'success': False, 
                'message': get_translation('period_overlap_error', get_language())
            }), 409
        
        # Update period
        schedule_period_repository.update_period(
            period=period,
            name=data['name'],
            start_date=start_date,
            end_date=end_date,
            is_active=is_active
        )
        
        return jsonify({
            'success': True,
            'message': get_translation('period_updated', get_language()),
            'period': {
                'id': period.id,
                'name': period.name,
                'start_date': period.start_date.strftime('%Y-%m-%d'),
                'end_date': period.end_date.strftime('%Y-%m-%d'),
                'is_active': period.is_active
            }
        })
    except Exception as e:
        logging.error(f"Error updating schedule period: {str(e)}")
        return jsonify({
            'success': False, 
            'message': get_translation('error_updating_period', get_language())
        }), 500

@schedules_bp.route('/api/delete/<int:period_id>', methods=['DELETE'])
@login_required
def api_delete(period_id):
    """API endpoint for deleting a schedule period."""
    try:
        period = schedule_period_repository.get_by_id(period_id, current_user.id)
        if not period:
            return jsonify({
                'success': False, 
                'message': get_translation('period_not_found', get_language())
            }), 404
        
        schedule_period_repository.delete(period)
        
        return jsonify({
            'success': True,
            'message': get_translation('period_deleted', get_language())
        })
    except Exception as e:
        logging.error(f"Error deleting schedule period: {str(e)}")
        return jsonify({
            'success': False, 
            'message': get_translation('error_deleting_period', get_language())
        }), 500

@schedules_bp.route('/api/days/update/<int:period_id>', methods=['POST'])
@login_required
def api_update_days(period_id):
    """API endpoint for updating day schedules."""
    try:
        period = schedule_period_repository.get_by_id(period_id, current_user.id)
        if not period:
            return jsonify({
                'success': False, 
                'message': get_translation('period_not_found', get_language())
            }), 404
            
        data = request.get_json()
        if not data or 'days' not in data:
            return jsonify({
                'success': False, 
                'message': get_translation('missing_required_fields', get_language())
            }), 400
            
        # Get existing day schedules
        existing_schedules = day_schedule_repository.get_all_by_period(period_id)
        
        # Delete existing day schedules
        for schedule in existing_schedules:
            day_schedule_repository.delete(schedule)
        
        # Add new day schedules from data
        day_schedules = []
        for day_data in data['days']:
            day_of_week = day_data.get('day_of_week')
            check_in_time = day_data.get('check_in_time')
            check_out_time = day_data.get('check_out_time')
            
            if day_of_week is not None and check_in_time and check_out_time:
                try:
                    day_of_week = int(day_of_week)
                    if day_of_week < 0 or day_of_week > 6:
                        continue
                except (ValueError, TypeError):
                    continue
                    
                day_schedule = day_schedule_repository.create_day_schedule(
                    period_id=period_id,
                    day_of_week=day_of_week,
                    check_in_time=check_in_time,
                    check_out_time=check_out_time
                )
                day_schedules.append({
                    'id': day_schedule.id,
                    'day_of_week': day_schedule.day_of_week,
                    'check_in_time': day_schedule.check_in_time,
                    'check_out_time': day_schedule.check_out_time
                })
        
        return jsonify({
            'success': True,
            'message': get_translation('day_schedules_updated', get_language()),
            'day_schedules': day_schedules
        })
    except Exception as e:
        logging.error(f"Error updating day schedules: {str(e)}")
        return jsonify({
            'success': False, 
            'message': get_translation('error_updating_schedules', get_language())
        }), 500

@schedules_bp.route('/partial')
@login_required
def partial():
    """Return partial HTML for schedule list to support AJAX updates."""
    periods = schedule_period_repository.get_all(current_user.id)
    return render_template('schedules/partials/schedule_list.html', periods=periods) 