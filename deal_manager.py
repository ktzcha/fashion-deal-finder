# Semi-Automated Deal Management System
# Manual curation with automated refresh capabilities

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import requests
from bs4 import BeautifulSoup
import json
import schedule
import time
from typing import Dict, List, Optional
import re

class DealManager:
    """Manages manually curated deals with automated price checking"""
    
    def __init__(self):
        self.deals_file = "curated_deals.json"
        self.deals = self.load_deals()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def load_deals(self) -> List[Dict]:
        """Load manually curated deals"""
        try:
            with open(self.deals_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            return []
    
    def save_deals(self):
        """Save deals to file"""
        with open(self.deals_file, 'w', encoding='utf-8') as f:
            json.dump(self.deals, f, indent=2, ensure_ascii=False, default=str)
    
    def add_manual_deal(self, deal_data: Dict):
        """Add a manually found deal"""
        deal = {
            'id': f"{deal_data['retailer']}_{len(self.deals)}_{int(time.time())}",
            'product_name': deal_data['product_name'],
            'brand': deal_data['brand'],
            'retailer': deal_data['retailer'],
            'current_price': deal_data['current_price'],
            'original_price': deal_data.get('original_price'),
            'product_url': deal_data['product_url'],
            'image_url': deal_data.get('image_url', ''),
            'sizes_available': deal_data.get('sizes_available', []),
            'category': deal_data.get('category', 'Fashion'),
            'gender': deal_data.get('gender', 'Unisex'),
            'manually_added': True,
            'added_date': datetime.now().isoformat(),
            'last_checked': datetime.now().isoformat(),
            'status': 'active',
            'notes': deal_data.get('notes', ''),
            'affiliate_link': deal_data.get('affiliate_link', ''),
            'discount_percentage': self.calculate_discount(
                deal_data.get('original_price'), 
                deal_data['current_price']
            )
        }
        
        self.deals.append(deal)
        self.save_deals()
        return deal['id']
    
    def calculate_discount(self, original_price: Optional[float], current_price: float) -> Optional[float]:
        """Calculate discount percentage"""
        if original_price and original_price > current_price:
            return round(((original_price - current_price) / original_price) * 100, 1)
        return None
    
    def extract_price_from_url(self, url: str, retailer: str) -> Optional[float]:
        """Extract current price from product URL"""
        try:
            response = self.session.get(url, timeout=10)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Retailer-specific price selectors
            price_selectors = {
                'zalando': [
                    '[data-testid="product-price"]',
                    '.ui-text-price',
                    'span[class*="price"]'
                ],
                'tommy_hilfiger': [
                    '.product-price',
                    '.price-current',
                    '[data-testid="price"]'
                ],
                'bijenkorf': [
                    '.product-price',
                    '.price',
                    '[class*="price"]'
                ],
                'generic': [
                    '[class*="price"]',
                    '[id*="price"]',
                    '.price',
                    'span[class*="amount"]'
                ]
            }
            
            selectors = price_selectors.get(retailer.lower(), price_selectors['generic'])
            
            for selector in selectors:
                price_elem = soup.select_one(selector)
                if price_elem:
                    price_text = price_elem.get_text(strip=True)
                    # Extract numeric price
                    price_match = re.search(r'[\d,]+\.?\d*', price_text.replace(',', ''))
                    if price_match:
                        return float(price_match.group())
            
            return None
            
        except Exception as e:
            st.warning(f"Error checking price for {url}: {str(e)}")
            return None
    
    def check_availability(self, url: str, retailer: str) -> bool:
        """Check if product is still available"""
        try:
            response = self.session.get(url, timeout=10)
            
            # Check for common "out of stock" indicators
            out_of_stock_indicators = [
                'out of stock',
                'niet beschikbaar',
                'uitverkocht',
                'temporarily unavailable',
                'product not available',
                'sold out'
            ]
            
            content = response.text.lower()
            for indicator in out_of_stock_indicators:
                if indicator in content:
                    return False
            
            # If we can fetch the page and no out-of-stock indicators, assume available
            return response.status_code == 200
            
        except Exception:
            return False
    
    def refresh_deal_prices(self, deal_ids: List[str] = None) -> Dict[str, str]:
        """Refresh prices for specified deals or all deals"""
        if deal_ids is None:
            deals_to_refresh = self.deals
        else:
            deals_to_refresh = [d for d in self.deals if d['id'] in deal_ids]
        
        refresh_results = {}
        
        for deal in deals_to_refresh:
            st.info(f"Checking: {deal['product_name']} at {deal['retailer']}")
            
            # Check current price
            current_price = self.extract_price_from_url(deal['product_url'], deal['retailer'])
            
            # Check availability
            is_available = self.check_availability(deal['product_url'], deal['retailer'])
            
            # Update deal data
            old_price = deal['current_price']
            deal['last_checked'] = datetime.now().isoformat()
            
            if current_price is not None:
                deal['current_price'] = current_price
                deal['discount_percentage'] = self.calculate_discount(
                    deal.get('original_price'), current_price
                )
                
                if current_price != old_price:
                    price_change = current_price - old_price
                    refresh_results[deal['id']] = f"Price changed: €{old_price} → €{current_price} ({price_change:+.2f})"
                else:
                    refresh_results[deal['id']] = "Price unchanged"
            else:
                refresh_results[deal['id']] = "Could not fetch price"
            
            # Update availability
            if not is_available:
                deal['status'] = 'out_of_stock'
                refresh_results[deal['id']] += " - OUT OF STOCK"
            else:
                deal['status'] = 'active'
            
            time.sleep(1)  # Be respectful with requests
        
        self.save_deals()
        return refresh_results
    
    def get_active_deals(self, sort_by: str = 'discount_percentage') -> List[Dict]:
        """Get all active deals sorted by specified criteria"""
        active_deals = [d for d in self.deals if d.get('status') == 'active']
        
        if sort_by == 'discount_percentage':
            return sorted(active_deals, 
                         key=lambda x: x.get('discount_percentage', 0), 
                         reverse=True)
        elif sort_by == 'added_date':
            return sorted(active_deals, 
                         key=lambda x: x.get('added_date', ''), 
                         reverse=True)
        elif sort_by == 'price':
            return sorted(active_deals, 
                         key=lambda x: x.get('current_price', 0))
        
        return active_deals
    
    def get_stale_deals(self, hours: int = 24) -> List[Dict]:
        """Get deals that haven't been checked recently"""
        cutoff = datetime.now() - timedelta(hours=hours)
        
        stale_deals = []
        for deal in self.deals:
            try:
                last_checked = datetime.fromisoformat(deal['last_checked'])
                if last_checked < cutoff:
                    stale_deals.append(deal)
            except:
                stale_deals.append(deal)  # If no last_checked, consider stale
        
        return stale_deals
    
    def remove_deal(self, deal_id: str):
        """Remove a deal by ID"""
        self.deals = [d for d in self.deals if d['id'] != deal_id]
        self.save_deals()

# Streamlit Interface for Deal Management
def deal_management_interface():
    """Streamlit interface for managing deals"""
    st.title("Fashion Deal Manager")
    
    deal_manager = DealManager()
    
    # Sidebar for actions
    st.sidebar.title("Actions")
    
    # Add new deal form
    with st.sidebar.expander("Add New Deal"):
        with st.form("add_deal"):
            product_name = st.text_input("Product Name*")
            brand = st.text_input("Brand*")
            retailer = st.selectbox("Retailer*", 
                                   ["Zalando", "Tommy Hilfiger", "de Bijenkorf", "Other"])
            current_price = st.number_input("Current Price (EUR)*", min_value=0.01, step=0.01)
            original_price = st.number_input("Original Price (EUR)", min_value=0.01, step=0.01)
            product_url = st.text_input("Product URL*")
            image_url = st.text_input("Image URL")
            affiliate_link = st.text_input("Affiliate Link")
            category = st.selectbox("Category", 
                                   ["Shirts", "Pants", "Jackets", "Shoes", "Accessories", "Other"])
            gender = st.selectbox("Gender", ["Men", "Women", "Unisex"])
            notes = st.text_area("Notes")
            
            if st.form_submit_button("Add Deal"):
                if product_name and brand and retailer and current_price and product_url:
                    deal_data = {
                        'product_name': product_name,
                        'brand': brand,
                        'retailer': retailer,
                        'current_price': current_price,
                        'original_price': original_price if original_price > 0 else None,
                        'product_url': product_url,
                        'image_url': image_url,
                        'affiliate_link': affiliate_link,
                        'category': category,
                        'gender': gender,
                        'notes': notes
                    }
                    
                    deal_id = deal_manager.add_manual_deal(deal_data)
                    st.success(f"Deal added with ID: {deal_id}")
                    st.experimental_rerun()
                else:
                    st.error("Please fill in all required fields (*)")
    
    # Refresh prices button
    if st.sidebar.button("Refresh All Prices"):
        with st.spinner("Refreshing prices..."):
            results = deal_manager.refresh_deal_prices()
            st.sidebar.success(f"Refreshed {len(results)} deals")
            for deal_id, result in results.items():
                st.sidebar.text(result)
    
    # Main content area
    tab1, tab2, tab3 = st.tabs(["Active Deals", "Deal Analytics", "Stale Deals"])
    
    with tab1:
        st.header("Active Deals")
        
        # Filters
        col1, col2, col3 = st.columns(3)
        with col1:
            sort_by = st.selectbox("Sort by", 
                                  ["discount_percentage", "added_date", "price"])
        with col2:
            min_discount = st.slider("Min Discount %", 0, 80, 10)
        with col3:
            retailer_filter = st.multiselect("Retailers", 
                                           ["Zalando", "Tommy Hilfiger", "de Bijenkorf"])
        
        # Get and filter deals
        active_deals = deal_manager.get_active_deals(sort_by)
        
        if min_discount > 0:
            active_deals = [d for d in active_deals 
                           if d.get('discount_percentage', 0) >= min_discount]
        
        if retailer_filter:
            active_deals = [d for d in active_deals 
                           if d['retailer'] in retailer_filter]
        
        # Display deals
        for deal in active_deals:
            with st.container():
                col1, col2, col3, col4 = st.columns([2, 2, 1, 1])
                
                with col1:
                    st.write(f"**{deal['product_name']}**")
                    st.write(f"Brand: {deal['brand']}")
                    st.write(f"Retailer: {deal['retailer']}")
                
                with col2:
                    st.write(f"Price: €{deal['current_price']}")
                    if deal.get('original_price'):
                        st.write(f"Was: €{deal['original_price']}")
                    if deal.get('discount_percentage'):
                        st.write(f"**{deal['discount_percentage']}% OFF**")
                
                with col3:
                    if st.button("View", key=f"view_{deal['id']}"):
                        st.write(f"URL: {deal['product_url']}")
                        if deal.get('affiliate_link'):
                            st.write(f"Affiliate: {deal['affiliate_link']}")
                
                with col4:
                    if st.button("Remove", key=f"remove_{deal['id']}"):
                        deal_manager.remove_deal(deal['id'])
                        st.experimental_rerun()
                
                st.divider()
    
    with tab2:
        st.header("Deal Analytics")
        
        active_deals = deal_manager.get_active_deals()
        
        if active_deals:
            # Create dataframe for analysis
            df = pd.DataFrame(active_deals)
            
            # Summary stats
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Active Deals", len(active_deals))
            with col2:
                avg_discount = df['discount_percentage'].fillna(0).mean()
                st.metric("Avg Discount %", f"{avg_discount:.1f}%")
            with col3:
                total_savings = df.apply(lambda x: 
                    (x.get('original_price', 0) - x['current_price']) 
                    if x.get('original_price') else
