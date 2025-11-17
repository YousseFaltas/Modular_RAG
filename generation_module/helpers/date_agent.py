import re
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import pytz

class DateAgent:
    def __init__(self, timezone: str = "Africa/Cairo"):
        self.timezone = pytz.timezone(timezone)
        
        # Date-related keywords and patterns
        self.date_keywords = [
            'today', 'tomorrow', 'yesterday', 'now', 'current', 'date', 'time',
            'when', 'what day', 'what time', 'this week', 'next week', 'last week',
            'this month', 'next month', 'last month', 'this year', 'next year',
            'اليوم', 'غدا', 'أمس', 'الآن', 'الحالي', 'التاريخ', 'الوقت',
            'متى', 'أي يوم', 'أي وقت', 'هذا الأسبوع', 'الأسبوع القادم', 'الأسبوع الماضي',
            'هذا الشهر', 'الشهر القادم', 'الشهر الماضي', 'هذا العام', 'العام القادم'
        ]
        
        # Relative date patterns
        self.relative_patterns = {
            'today': 0,
            'tomorrow': 1,
            'yesterday': -1,
            'اليوم': 0,
            'غدا': 1,
            'أمس': -1
        }
    
    def is_date_related_query(self, query: str) -> bool:
        query_lower = query.lower()
        return any(keyword in query_lower for keyword in self.date_keywords)
    
    def get_current_datetime(self) -> Dict[str, Any]:
        now = datetime.now(self.timezone)
        
        return {
            'datetime': now,
            'date': now.strftime('%Y-%m-%d'),
            'time': now.strftime('%H:%M:%S'),
            'day_name': now.strftime('%A'),
            'month_name': now.strftime('%B'),
            'year': now.year,
            'formatted_date': now.strftime('%A, %B %d, %Y'),
            'formatted_time': now.strftime('%I:%M %p'),
            'timezone': str(self.timezone)
        }
    
    def parse_relative_date(self, query: str) -> Optional[datetime]:
        query_lower = query.lower()
        now = datetime.now(self.timezone)
        
        for pattern, days_offset in self.relative_patterns.items():
            if pattern in query_lower:
                target_date = now + timedelta(days=days_offset)
                return target_date
        
        # Handle "next week" / "الأسبوع القادم"
        if 'next week' in query_lower or 'الأسبوع القادم' in query_lower:
            days_until_next_week = 7 - now.weekday()
            return now + timedelta(days=days_until_next_week)
        
        # Handle "last week" / "الأسبوع الماضي"
        if 'last week' in query_lower or 'الأسبوع الماضي' in query_lower:
            days_to_last_week = now.weekday() + 7
            return now - timedelta(days=days_to_last_week)
        
        return None
    
    def enhance_context_with_date(self, context: str, query: str) -> str:
        if not self.is_date_related_query(query):
            return context
        
        current_info = self.get_current_datetime()
        relative_date = self.parse_relative_date(query)
        
        date_context = f"\n\nCURRENT DATE AND TIME INFORMATION:\n"
        date_context += f"Current Date: {current_info['formatted_date']}\n"
        date_context += f"Current Time: {current_info['formatted_time']}\n"
        date_context += f"Timezone: {current_info['timezone']}\n"
        
        if relative_date:
            date_context += f"Requested Date: {relative_date.strftime('%A, %B %d, %Y')}\n"
        
        return context + date_context
    
    def enhance_prompt_with_date_instructions(self, template: str) -> str:
        date_instructions = """
- If the user asks about current date, time, or day, use the provided current date and time information.
- For relative date queries (today, tomorrow, yesterday, etc.), calculate and provide the appropriate date.
- Always provide dates in a clear, user-friendly format.
- If asked about business hours or schedules, mention that specific business information should be checked with Beltone directly.
"""
        
        # Insert date instructions before the context section
        if "Context:" in template:
            return template.replace("Context:", date_instructions + "\nContext:")
        else:
            return date_instructions + "\n" + template

