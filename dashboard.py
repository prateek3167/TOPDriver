
import streamlit as st
import pandas as pd
import plotly.express as px
from db_engine import get_engine

st.set_page_config(page_title="Support Ticket Analytics", layout="wide")

@st.cache_data(ttl=600)
def fetch_data():
    engine = get_engine()
    query = """
        SELECT 
            ticket_id,
            created_time,
            closed_time,
            product,
            category,
            ticket_owner,
            classifications,
            resolution_time_days
        FROM support_tickets;
    """
    df = pd.read_sql(query, engine)
    df['created_time'] = pd.to_datetime(df['created_time'])
    df['closed_time'] = pd.to_datetime(df['closed_time'])
    return df

st.title("📊 Support Ticket Operations Dashboard")
df = fetch_data()

#Sidebar Filters
st.sidebar.header("Global Filters")
min_date = df['created_time'].dt.date.min()
max_date = df['created_time'].dt.date.max()

date_range = st.sidebar.date_input("Date Range", [min_date, max_date])

products = ["All"] + sorted([p for p in df['product'].dropna().unique()])
selected_product = st.sidebar.selectbox("Product", products)

#Apply Filters
filtered_df = df.copy()
if len(date_range) == 2:
    start_d, end_d = date_range
    filtered_df = filtered_df[
        (filtered_df['created_time'].dt.date >= start_d) & 
        (filtered_df['created_time'].dt.date <= end_d)
    ]

if selected_product != "All":
    filtered_df = filtered_df[filtered_df['product'] == selected_product]

#Top KPI Metrics
col1, col2, col3, col4 = st.columns(4)
total_tickets = len(filtered_df)
closed_tickets = filtered_df['closed_time'].notnull().sum()
open_tickets = total_tickets - closed_tickets
avg_res_time = filtered_df['resolution_time_days'].dropna().mean()

col1.metric("Total Tickets", f"{total_tickets:,}")
col2.metric("Closed Tickets", f"{closed_tickets:,}")
col3.metric("Pending / Open", f"{open_tickets:,}")
col4.metric("Avg Resolution Time", f"{avg_res_time:.1f} Days" if pd.notnull(avg_res_time) else "N/A")

st.markdown("---")

#Visualizations Row 1
r1_col1, r1_col2 = st.columns(2)

with r1_col1:
    st.subheader("Daily Ticket Volume Trend")
    trend = filtered_df.groupby(filtered_df['created_time'].dt.date).size().reset_index(name='count')
    fig_trend = px.line(trend, x='created_time', y='count', title="Daily Inflow", markers=True)
    fig_trend.update_layout(xaxis_title="Date", yaxis_title="Tickets")
    st.plotly_chart(fig_trend, use_container_width=True)

with r1_col2:
    st.subheader("Top 10 Problem Categories")
    top_categories = filtered_df['category'].value_counts().head(10).reset_index()
    top_categories.columns = ['Category', 'Count']
    fig_cat = px.bar(top_categories, x='Count', y='Category', orientation='h', title="Tickets by Category")
    fig_cat.update_layout(yaxis={'categoryorder':'total ascending'})
    st.plotly_chart(fig_cat, use_container_width=True)

#Visualizations Row 2
r2_col1, r2_col2 = st.columns(2)

with r2_col1:
    st.subheader("Volume by Product")
    prod_counts = filtered_df['product'].value_counts().head(8).reset_index()
    prod_counts.columns = ['Product', 'Count']
    fig_prod = px.pie(prod_counts, names='Product', values='Count', hole=0.4)
    st.plotly_chart(fig_prod, use_container_width=True)

with r2_col2:
    st.subheader("Top 10 Ticket Owners (Resolution Distribution)")
    owner_counts = filtered_df['ticket_owner'].value_counts().head(10).reset_index()
    owner_counts.columns = ['Ticket Owner', 'Count']
    fig_owner = px.bar(owner_counts, x='Ticket Owner', y='Count', title="Resolved by Owner")
    st.plotly_chart(fig_owner, use_container_width=True)
