from fastapi import FastAPI, HTTPException, Query
import requests
import os
import uvicorn
from typing import Optional, List, Dict, Any

app = FastAPI(
    title="CoinGecko API Wrapper",
    description="Optimized API wrapper for CoinGecko with filters for ChatGPT",
    version="2.0.0"
)

BASE_URL = "https://api.coingecko.com/api/v3"

def fetch_from_coingecko(endpoint: str, params: Optional[Dict[str, Any]] = None):
    url = f"{BASE_URL}{endpoint}"
    
    headers = {
        "Accept": "application/json",
        "User-Agent": "CoinGecko-API-Wrapper/2.0"
    }
    
    try:
        response = requests.get(url, params=params, headers=headers)
        
        if response.status_code == 200:
            return response.json()
        else:
            response.raise_for_status()
    except requests.RequestException as e:
        raise HTTPException(status_code=response.status_code if hasattr(e, 'response') and e.response else 500, detail=str(e))

@app.get("/")
def home():
    return {
        "message": "✅ CoinGecko API Wrapper is running!",
        "version": "2.0.0",
        "documentation": "/docs"
    }

# Endpoint بهینه شده برای لیست کوین‌ها با جستجو
@app.get("/coins/search")
def search_coins(
    query: str = Query(..., description="Search by name or symbol"),
    limit: int = Query(10, ge=1, le=50, description="Number of results to return")
):
    """Search for coins by name or symbol"""
    all_coins = fetch_from_coingecko("/coins/list")
    
    # فیلتر بر اساس query
    matching_coins = []
    query_lower = query.lower()
    
    for coin in all_coins:
        if (query_lower in coin.get('name', '').lower() or 
            query_lower in coin.get('symbol', '').lower() or
            query_lower == coin.get('id', '').lower()):
            matching_coins.append(coin)
            
    # محدود کردن تعداد نتایج
    return matching_coins[:limit]

# جزئیات کوین با فیلتر
@app.get("/coins/{id}/filtered")
def get_coin_data_filtered(
    id: str,
    fields: Optional[str] = Query(
        "name,symbol,market_data.current_price,market_data.market_cap,market_data.price_change_percentage_24h",
        description="Comma-separated fields to include"
    )
):
    """Get filtered coin data"""
    full_data = fetch_from_coingecko(f"/coins/{id}", {
        "localization": "false",
        "tickers": "false",
        "market_data": "true",
        "community_data": "false",
        "developer_data": "false",
        "sparkline": "false"
    })
    
    # فیلتر کردن فیلدها
    if fields:
        fields_list = [f.strip() for f in fields.split(',')]
        filtered_data = {}
        
        for field in fields_list:
            # پشتیبانی از فیلدهای تو در تو
            parts = field.split('.')
            source_data = full_data
            target_data = filtered_data
            
            for i, part in enumerate(parts):
                if i == len(parts) - 1:  # آخرین بخش
                    if part in source_data:
                        target_data[part] = source_data[part]
                else:
                    if part in source_data:
                        if part not in target_data:
                            target_data[part] = {}
                        source_data = source_data[part]
                        target_data = target_data[part]
                    else:
                        break
        
        return filtered_data
    
    return full_data

# ترندینگ با فیلتر
@app.get("/search/trending/filtered")
def get_trending_filtered(
    limit: int = Query(7, ge=1, le=20, description="Number of trending coins"),
    fields: Optional[str] = Query(
        "name,symbol,price_btc,market_cap_rank", 
        description="Fields to include"
    )
):
    """Get trending coins with filtered data"""
    trending_data = fetch_from_coingecko("/search/trending")
    
    if trending_data and "coins" in trending_data:
        filtered_coins = []
        
        for coin_data in trending_data["coins"][:limit]:
            coin = coin_data.get("item", {})
            filtered_coin = {}
            
            # استخراج داده‌های مورد نظر
            if "name" in fields:
                filtered_coin["name"] = coin.get("name")
            if "symbol" in fields:
                filtered_coin["symbol"] = coin.get("symbol")
            if "price_btc" in fields:
                filtered_coin["price_btc"] = coin.get("price_btc")
            if "market_cap_rank" in fields:
                filtered_coin["market_cap_rank"] = coin.get("market_cap_rank")
            
            # درخواست قیمت USD اگر نیاز باشد
            if "price_usd" in fields or "price_change_24h" in fields:
                try:
                    price_data = fetch_from_coingecko("/simple/price", {
                        "ids": coin.get("id"),
                        "vs_currencies": "usd",
                        "include_24hr_change": "true"
                    })
                    
                    if price_data and coin.get("id") in price_data:
                        if "price_usd" in fields:
                            filtered_coin["price_usd"] = price_data[coin.get("id")].get("usd")
                        if "price_change_24h" in fields:
                            filtered_coin["price_change_24h"] = price_data[coin.get("id")].get("usd_24h_change")
                except:
                    pass
            
            filtered_coins.append(filtered_coin)
        
        return {"coins": filtered_coins}
    
    return trending_data

# داده‌های بازار با pagination
@app.get("/coins/markets/paginated")
def get_coins_markets_paginated(
    vs_currency: str = Query("usd"),
    per_page: int = Query(20, ge=1, le=100),
    page: int = Query(1, ge=1),
    order: str = Query("market_cap_desc"),
    category: Optional[str] = Query(None),
    ids: Optional[str] = Query(None),
    fields: Optional[str] = Query(
        "id,symbol,name,current_price,market_cap,price_change_percentage_24h",
        description="Fields to include in response"
    )
):
    """Get market data with pagination and field filtering"""
    params = {
        "vs_currency": vs_currency,
        "order": order,
        "per_page": per_page,
        "page": page,
        "sparkline": "false"
    }
    
    if category:
        params["category"] = category
    if ids:
        params["ids"] = ids
    
    market_data = fetch_from_coingecko("/coins/markets", params)
    
    # فیلتر کردن فیلدها
    if fields and isinstance(market_data, list):
        fields_list = [f.strip() for f in fields.split(',')]
        filtered_data = []
        
        for coin in market_data:
            filtered_coin = {}
            for field in fields_list:
                if field in coin:
                    filtered_coin[field] = coin[field]
            filtered_data.append(filtered_coin)
        
        return filtered_data
    
    return market_data

# قیمت ساده با فرمت بهتر
@app.get("/simple/price/formatted")
def get_simple_price_formatted(
    ids: str = Query(..., description="Coin ids comma-separated"),
    vs_currencies: str = Query("usd", description="Target currencies"),
    include_change: bool = Query(False, description="Include 24h change")
):
    """Get formatted price data"""
    params = {
        "ids": ids,
        "vs_currencies": vs_currencies,
        "include_24hr_change": str(include_change).lower()
    }
    
    price_data = fetch_from_coingecko("/simple/price", params)
    
    # فرمت‌بندی بهتر
    formatted_data = []
    for coin_id, data in price_data.items():
        formatted_coin = {
            "id": coin_id,
            "prices": {}
        }
        
        for currency, price in data.items():
            if not currency.endswith("_24h_change"):
                formatted_coin["prices"][currency] = price
                
                # اضافه کردن تغییر 24 ساعته اگر موجود باشد
                change_key = f"{currency}_24h_change"
                if change_key in data:
                    formatted_coin["prices"][f"{currency}_change_24h"] = data[change_key]
        
        formatted_data.append(formatted_coin)
    
    return formatted_data

# خلاصه‌ای از اطلاعات کوین
@app.get("/coins/{id}/summary")
def get_coin_summary(id: str):
    """Get coin summary with essential data only"""
    full_data = fetch_from_coingecko(f"/coins/{id}", {
        "localization": "false",
        "tickers": "false",
        "market_data": "true",
        "community_data": "false",
        "developer_data": "false",
        "sparkline": "false"
    })
    
    # استخراج اطلاعات مهم
    summary = {
        "id": full_data.get("id"),
        "symbol": full_data.get("symbol"),
        "name": full_data.get("name"),
        "current_price": full_data.get("market_data", {}).get("current_price", {}).get("usd"),
        "market_cap": full_data.get("market_data", {}).get("market_cap", {}).get("usd"),
        "market_cap_rank": full_data.get("market_cap_rank"),
        "price_change_24h": full_data.get("market_data", {}).get("price_change_percentage_24h"),
        "total_volume": full_data.get("market_data", {}).get("total_volume", {}).get("usd"),
        "circulating_supply": full_data.get("market_data", {}).get("circulating_supply"),
        "max_supply": full_data.get("market_data", {}).get("max_supply"),
        "ath": full_data.get("market_data", {}).get("ath", {}).get("usd"),
        "ath_date": full_data.get("market_data", {}).get("ath_date", {}).get("usd")
    }
    
    return summary

# لیست دسته‌بندی‌ها به صورت ساده
@app.get("/coins/categories/simple")
def get_categories_simple():
    """Get simple list of categories"""
    categories = fetch_from_coingecko("/coins/categories/list")
    # فقط نام و id برگردان
    return [{"id": cat.get("category_id"), "name": cat.get("name")} for cat in categories]

# جستجوی ساده
@app.get("/search/simple")
def search_simple(
    query: str = Query(..., description="Search query"),
    limit: int = Query(5, ge=1, le=20)
):
    """Simple search with limited results"""
    search_results = fetch_from_coingecko("/search", {"query": query})
    
    # محدود کردن نتایج
    limited_results = {
        "coins": search_results.get("coins", [])[:limit],
        "exchanges": search_results.get("exchanges", [])[:limit],
        "categories": search_results.get("categories", [])[:limit]
    }
    
    return limited_results

# Run the server
if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    
    print(f"🚀 Starting CoinGecko API Wrapper v2 on 0.0.0.0:{port}")
    print(f"📚 API Documentation: http://0.0.0.0:{port}/docs")
    
    uvicorn.run(
        "main:app", 
        host="0.0.0.0", 
        port=port
    )
