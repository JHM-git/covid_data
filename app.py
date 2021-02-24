import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt
import altair as alt
import datetime
from bs4 import BeautifulSoup
import requests
import re

# Data - cache para agilizar el proceso al cambiar los selectores
@st.cache(allow_output_mutation=True)
def get_data():
    data = pd.read_json('https://datos.comunidad.madrid/catalogo/dataset/b3d55e40-8263-4c0b-827d-2bb23b5e7bab/resource/907a2df0-2334-4ca7-aed6-0fa199c893ad/download/covid19_tia_zonas_basicas_salud_s.json', orient='split')
    return data

# Data sobre las zonas con restricciones - cache para agilizar el proceso
@st.cache
def restricted_zones():
    restrictions_url = 'https://www.comunidad.madrid/covid-19'
    req = requests.get(restrictions_url)
    soup = BeautifulSoup(req.text, 'html.parser')
    search = soup.find_all(string=re.compile("ZBS "))
    date = soup.find_all(string=re.compile(" 2021"))
    # El punto de división entre zonas de Madrid y de otros municipios (para uso futuro)
    list_divider = re.search('\d', search[0])
    list_divider = int(list_divider.group(0))
    restrictions_str = ''.join(search)
    zbs_restrictions = re.findall(r"ZBS.+?(?=[\;\,\(\)Z])", restrictions_str)
    zbs_restrictions = [zbs[4:].strip() for zbs in zbs_restrictions]
    zbs_restrictions = [zbs[:-1].rstrip() if zbs[-1] == 'y' else zbs for zbs in zbs_restrictions]
    return zbs_restrictions, date[0]

# Título más presentación de la app; indicaciones de uso
st.title('Incidencia del covid-19 en Madrid')
st.markdown('''Con esta aplicación puedes ver facilmente los últimos datos de la incidencia
del Covid-19 por zonas básicas de Salud de Madrid, y si hay restricciones en vigor en la zona. En los gráficos puedes comparar las cifras con
otras zonas y con la media entre las zonas, y ver la relación entre acumulación de casos reciente y total.''')
st.markdown('''Utiliza los selectores para elegir la zona. También puedes especificar fechas 
para el gráfico.''')
st.markdown('En un móvil pulse la flecha a la izquierda para ver los selectores.')
st.markdown('Los datos se actualizan semanalmente.')
st.markdown('***')

# Recuperación de los datos y su procesamiento
try:
    data = get_data()
except:
    data = None
try:
    zbs_restrictions, restrictions_date = restricted_zones()
except:
    zbs_restrictions, restrictions_date = [], None 

if data is not None:
    ZBS = pd.unique(data['zona_basica_salud'])
    DATES = pd.unique(data['fecha_informe'])
    DATES = DATES[::-1]
    most_recent = data[data['fecha_informe'] == DATES[-1]]
    data['date'] = pd.to_datetime(data['fecha_informe'])
    data['date'] = data['date'].dt.date
    clean_dates = pd.unique(data['date'])
    clean_dates = clean_dates[::-1]
    dates_as_list = clean_dates.tolist()
    MEAN = data.groupby('fecha_informe')['tasa_incidencia_acumulada_ultimos_14dias'].mean()

date = datetime.datetime.now()

# En caso de problema con el data y/o conexión
if data is None:
    st.markdown('''Lo sentimos, pero hay un problema con la conexión\n
    Vuelve a intentar más tarde''')

# Visualización siempre cuando no hay problema con el data
if data is not None:
    # Sidebar
    st.sidebar.title('Elige zona/s para ver los datos')
    zone_selection = st.sidebar.multiselect('Elige zona/s básica/s de salud (máximo 10)', ZBS)
    if len(zone_selection) > 10:
        st.sidebar.write('Solo se visualizan los datos de diez zonas.')
        zone_selection = zone_selection[:10]
    time_beginning = st.sidebar.select_slider('Elige fecha de inicio para el gráfico (año-mes-día)', dates_as_list[:], value=dates_as_list[-26])
    start_index = dates_as_list.index(time_beginning)
    time_ending = st.sidebar.select_slider('Elige fecha final para el gráfico (año-mes-día)', dates_as_list[start_index+1:], value=dates_as_list[-1])
    end_index = dates_as_list.index(time_ending)

    # Información sobre zonas seleccionadas
    if len(zone_selection) == 1:
        st.header('Los datos de la zona elegida')
    else:
        st.header('Los datos de las zonas elegidas')
    if len(zone_selection) == 0:
        st.markdown('Todavía no has elegido ninguna zona.')
    latest_date = str(clean_dates[-1])
    latest_date = f'{latest_date[-2:]}/{latest_date[-5:-3]}/{latest_date[:-6]}'

    for selection in zone_selection:
        selection_info = most_recent[most_recent['zona_basica_salud'] == selection]
        last_two_weeks = selection_info['tasa_incidencia_acumulada_ultimos_14dias'].values[0]
        previous_week = data['tasa_incidencia_acumulada_ultimos_14dias'][(data['fecha_informe'] == DATES[-2]) & (data['zona_basica_salud'] == selection)].values[0]
        difference = round((last_two_weeks - previous_week) / previous_week * 100, 1)
        change = ''
        if difference > 0:
            change = f'La incidencia ha subido **{difference}** por cien en la última semana.'
        elif difference < 0:
            change = f'La incidencia ha bajado **{abs(difference)}** por cien en la última semana.'
        else:
            change = 'La incidencia no ha cambiado en la última semana.'
        if selection in zbs_restrictions:
            restrictions = f'**Restricciones** de entradas y salidas en vigor en la semana del {restrictions_date}\n'
        else:
            restrictions = ''
        st.markdown(f'''
        ### {selection}:   (datos del {latest_date})\n
        {restrictions}
        Casos en las últimas dos semanas: **{int(selection_info['casos_confirmados_ultimos_14dias'].values[0])}**\n
        Casos por cien mil habitantes en las últimas dos semanas: **{round(selection_info['tasa_incidencia_acumulada_ultimos_14dias'].values[0], 2)}**\n
        Casos confirmados desde mayo de 2020: **{int(selection_info['casos_confirmados_totales'].values[0])}**\n
        Incidencia total por cien mil habitantes: **{round(selection_info['tasa_incidencia_acumulada_total'].values[0], 2)}**\n
        {change}
        ***
        '''
        )
        

    # Gráfico
    st.header('Evolución de la incidencia')
    st.write('')
    X = clean_dates[start_index:end_index+1]
    Ymean = MEAN[start_index:end_index+1]
    plt.figure(figsize=(16, 9))
    plt.plot(X, Ymean, 'r', label='Media zonas básicas de salud')
    for selection in zone_selection:
        Ysel = data[data['zona_basica_salud'] == selection]['tasa_incidencia_acumulada_ultimos_14dias'][::-1]
        Ysel = Ysel[start_index:end_index+1]
        plt.plot(X, Ysel, label=selection)
    plt.ylabel('Casos por cien mil habitantes en los últimos 14 días', fontsize=18.0)
    plt.xlabel('Fecha (año/mes)', fontsize=18.0)
    plt.yticks(fontsize=14.0)
    plt.xticks(rotation=45.0, fontsize=12.0)
    plt.legend(fontsize=14.0)

    st.pyplot(plt)

    # Scatter plot
    x_style = alt.Axis(title='Incidencia Acumulada Total', titleFontSize=14, titleFontWeight=500, labelFontSize=11)
    y_style = alt.Axis(title='Incidencia Acumulada Últimos 14 Días', titleFontSize=14, titleFontWeight=500, labelFontSize=11)
    x_axis = alt.X('tasa_incidencia_acumulada_total', axis=x_style)
    y_axis = alt.Y('tasa_incidencia_acumulada_ultimos_14dias', axis=y_style)
    scatter = alt.Chart(most_recent, height=400).mark_point().encode(x_axis, y_axis, tooltip='zona_basica_salud')
    st.header('Relación por incidencia acumulado total y reciente')
    st.write('')
    st.altair_chart(scatter, use_container_width=True)

    st.markdown('Fuente: Comunidad de Madrid')

# Footer 
st.markdown('***')
st.markdown(f'por H Makela | Madrid | {date.year}')