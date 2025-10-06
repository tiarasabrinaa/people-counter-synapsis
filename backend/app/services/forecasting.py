import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)

try:
    from prophet import Prophet
    PROPHET_AVAILABLE = True
except ImportError:
    PROPHET_AVAILABLE = False
    logger.warning("Prophet not available, using simple forecasting")


class ForecastingService:
    """Service for time series forecasting of people counting"""
    
    def __init__(self):
        self.model = None
    
    async def generate_forecast(
        self,
        db,
        area_name: Optional[str] = None,
        periods: int = 24
    ) -> List[dict]:
        """
        Generate forecast for people counting
        
        Args:
            db: Database instance
            area_name: Area to forecast (None for all areas)
            periods: Number of hours to forecast
            
        Returns:
            List of forecast points with timestamp and predicted count
        """
        try:
            # Get historical data (last 30 days)
            historical_data = await self._get_historical_data(db, area_name, days=30)
            
            if len(historical_data) < 24:  # Need at least 24 hours of data
                logger.warning(f"Insufficient data for forecasting: {len(historical_data)} hours")
                return self._generate_simple_forecast(periods)
            
            # Use Prophet if available, otherwise simple forecasting
            if PROPHET_AVAILABLE:
                return await self._prophet_forecast(historical_data, periods)
            else:
                return await self._simple_forecast(historical_data, periods)
                
        except Exception as e:
            logger.error(f"Error generating forecast: {e}")
            return self._generate_simple_forecast(periods)
    
    async def _get_historical_data(
        self,
        db,
        area_name: Optional[str],
        days: int = 30
    ) -> pd.DataFrame:
        """Get historical hourly data from database"""
        from app.config import settings
        
        # Calculate time range
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(days=days)
        
        # Build match filter
        match_filter = {"timestamp": {"$gte": start_time, "$lte": end_time}}
        if area_name:
            match_filter["area_name"] = area_name
        
        # Aggregate hourly entry counts
        pipeline = [
            {"$match": match_filter},
            {
                "$group": {
                    "_id": {
                        "year": {"$year": "$timestamp"},
                        "month": {"$month": "$timestamp"},
                        "day": {"$dayOfMonth": "$timestamp"},
                        "hour": {"$hour": "$timestamp"},
                        "event_type": "$event_type"
                    },
                    "count": {"$sum": 1}
                }
            },
            {"$sort": {"_id": 1}}
        ]
        
        results = await db[settings.COLLECTION_COUNTING].aggregate(pipeline).to_list(None)
        
        # Convert to DataFrame
        data = []
        for r in results:
            dt = datetime(
                r["_id"]["year"],
                r["_id"]["month"],
                r["_id"]["day"],
                r["_id"]["hour"]
            )
            event_type = r["_id"]["event_type"]
            count = r["count"]
            
            data.append({
                "ds": dt,
                "event_type": event_type,
                "count": count
            })
        
        if not data:
            return pd.DataFrame(columns=["ds", "y"])
        
        df = pd.DataFrame(data)
        
        # Pivot to get net count (entry - exit)
        df_pivot = df.pivot_table(
            index="ds",
            columns="event_type",
            values="count",
            fill_value=0
        ).reset_index()
        
        # Calculate net count
        if "entry" in df_pivot.columns:
            df_pivot["y"] = df_pivot.get("entry", 0) - df_pivot.get("exit", 0)
        else:
            df_pivot["y"] = 0
        
        return df_pivot[["ds", "y"]]
    
    async def _prophet_forecast(
        self,
        historical_data: pd.DataFrame,
        periods: int
    ) -> List[dict]:
        """Generate forecast using Prophet"""
        try:
            # Initialize Prophet model
            model = Prophet(
                daily_seasonality=True,
                weekly_seasonality=True,
                yearly_seasonality=False,
                changepoint_prior_scale=0.05,
                interval_width=0.95
            )
            
            # Fit model
            model.fit(historical_data)
            
            # Create future dataframe
            future = model.make_future_dataframe(periods=periods, freq='H')
            
            # Predict
            forecast = model.predict(future)
            
            # Get only future predictions
            forecast_future = forecast.tail(periods)
            
            # Format results
            results = []
            for _, row in forecast_future.iterrows():
                results.append({
                    "timestamp": row["ds"],
                    "predicted_count": max(0, float(row["yhat"])),  # Can't be negative
                    "lower_bound": max(0, float(row["yhat_lower"])),
                    "upper_bound": max(0, float(row["yhat_upper"]))
                })
            
            return results
            
        except Exception as e:
            logger.error(f"Prophet forecast error: {e}")
            return self._generate_simple_forecast(periods)
    
    async def _simple_forecast(
        self,
        historical_data: pd.DataFrame,
        periods: int
    ) -> List[dict]:
        """Simple forecasting based on moving average and trend"""
        try:
            # Calculate moving average (last 7 days)
            recent_avg = historical_data.tail(7 * 24)["y"].mean()
            
            # Calculate trend
            if len(historical_data) > 48:
                first_half_avg = historical_data.head(len(historical_data) // 2)["y"].mean()
                second_half_avg = historical_data.tail(len(historical_data) // 2)["y"].mean()
                trend = (second_half_avg - first_half_avg) / (len(historical_data) // 2)
            else:
                trend = 0
            
            # Calculate hourly pattern (average by hour of day)
            historical_data['hour'] = historical_data['ds'].dt.hour
            hourly_pattern = historical_data.groupby('hour')['y'].mean().to_dict()
            
            # Generate forecast
            results = []
            last_time = historical_data['ds'].max()
            
            for i in range(1, periods + 1):
                future_time = last_time + timedelta(hours=i)
                hour = future_time.hour
                
                # Base prediction: moving average + trend + hourly pattern
                hourly_factor = hourly_pattern.get(hour, recent_avg) / recent_avg if recent_avg > 0 else 1
                predicted = max(0, recent_avg + (trend * i) * hourly_factor)
                
                # Add some variance for confidence interval
                std_dev = historical_data["y"].std()
                
                results.append({
                    "timestamp": future_time,
                    "predicted_count": float(predicted),
                    "lower_bound": max(0, float(predicted - 1.96 * std_dev)),
                    "upper_bound": float(predicted + 1.96 * std_dev)
                })
            
            return results
            
        except Exception as e:
            logger.error(f"Simple forecast error: {e}")
            return self._generate_simple_forecast(periods)
    
    def _generate_simple_forecast(self, periods: int) -> List[dict]:
        """Generate simple constant forecast when no data available"""
        results = []
        current_time = datetime.utcnow()
        
        for i in range(1, periods + 1):
            future_time = current_time + timedelta(hours=i)
            results.append({
                "timestamp": future_time,
                "predicted_count": 10.0,  # Default prediction
                "lower_bound": 5.0,
                "upper_bound": 15.0
            })
        
        return results