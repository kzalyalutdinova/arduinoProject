import numpy as np
import math

data = [
    (0.74, 27), (0.747, 32), (0.659, 37), (0.596, 41),
    (0.557, 44), (0.527, 46), (0.503, 47), (0.493, 49),
    (0.488, 49), (0.503, 49)
]

B = 3980.0
T0 = 298.15
R0 = 2000.0
M = 0.03995
P_ATM = 101325.0
R_GAS = 8.314

# Коэффициенты для формулы массового расхода (кг/ч)
MAF_A, MAF_B, MAF_C = 38.75, -89.25, 51.45

# Коэффициенты для формулы температуры (°C)
TEMP_A, TEMP_B, TEMP_C = -15.3267, -56.9575, 80.5282

# V = np.array([d[0] for d in data])
# T = np.array([d[1] for d in data])
# coeffs = np.polyfit(V, T, 2)
# print(f"a={coeffs[0]:.4f}, b={coeffs[1]:.4f}, c={coeffs[2]:.4f}")

def voltage_to_temp(voltage):
    t_celsius = TEMP_A * voltage**2 + TEMP_B * voltage + TEMP_C
    t_kelvin = t_celsius + 273.15

    return t_celsius

def voltage_to_flow(voltage):
    curr_flow = 38.75 * voltage**2 - 89.25 * voltage + 53.75 - 2.3
    return curr_flow

def air_density(temp_kelvin, p_atm=P_ATM, m=M, r_gas=R_GAS, m_gas=M):
    return (p_atm * m_gas) / (r_gas * temp_kelvin)

# Объёмный расход 
def vol_flow(flow, air_density):
    vol_flow = flow / air_density
    return vol_flow

def var_2(curr_flow_v, temp_v):
    curr_flow = 38.75 * curr_flow_v ** 2   - 89.25 * curr_flow_v + 53.75 - 2.3;
    curr_temp_v = temp_v * 2500 / (5 - temp_v)
    curr_temp_k = 1.0 / (1.0/T0 + (1.0/B) * math.log(curr_temp_v / R0)) - 273;
    rho = (P_ATM * M) / (R_GAS * curr_temp_k)
    x = (curr_flow / rho)

    return curr_temp_k, x

# 2 варианта для ДМРВ
# Вариант 1 хуже по дисперсии, по умолчанию используется вариант 2
def dmrv_var1(curr_flow_v, temp_v):
    if curr_temp_v >= 5.0:
        curr_temp_v = 4.999
    elif curr_temp_v <= 0.0:
        curr_temp_v = 0.001
    
    temp_v1 = voltage_to_temp(curr_flow_v)
    flow_v1 = voltage_to_flow(temp_v)
    result = vol_flow(flow_v1, air_density(temp_v1))

    return result

def dmrv_var2(curr_flow_v, temp_v):
    if temp_v >= 5.0:
        temp_v = 4.999
    elif temp_v <= 0.0:
        temp_v = 1e-3
    
    curr_flow = 38.75 * curr_flow_v ** 2   - 89.25 * curr_flow_v + 53.75 - 2.3;
    curr_temp_v = temp_v * 2500 / (5 - temp_v)

    log_arg = curr_temp_v / R0
    if log_arg <= 0:
        log_arg = 1e-6
    
    curr_temp_k = 1.0 / (1.0/T0 + (1.0/B) * math.log(log_arg)) - 273;
    rho = (P_ATM * M) / (R_GAS * curr_temp_k)
    x = (curr_flow / rho)

    return x

if __name__ == "__main__":
    raw_data = [
        (3.618, 0.732), (3.643, 0.645), (3.599, 0.596), (3.55, 0.552),
        (3.521, 0.527), (3.579, 0.513), (3.511, 0.503), (3.574, 0.498),
        (3.54, 0.493), (3.506, 0.488), (3.545, 0.493), (3.555, 0.493),
        (3.55, 0.498), (3.496, 0.483), (3.486, 0.488)
    ]
    results_v1 = []
    results_v2 = []
    temps_v1 = []
    temps_v2 = []

    for volt_1, volt_2 in raw_data:
        temp_v1 = voltage_to_temp(volt_2)
        flow_v1 = voltage_to_flow(volt_1)

        result_v1 = vol_flow(flow_v1, air_density(temp_v1))
        temp_v2, result_v2 = var_2(volt_1, volt_2)

        temps_v1.append(temp_v1)
        temps_v2.append(temp_v2)
        results_v1.append(result_v1)
        results_v2.append(result_v2)

        print(f'Temperatures (°C): {temp_v1:.2f} | {temp_v2:.2f}')
        print(f'MAF: {result_v1:.2f} | {result_v2:.2f}\n')
    
    var1, var2 = np.var(np.array(results_v1), ddof=1), np.var(np.array(results_v2), ddof=1)
    std1, std2 = np.std(np.array(results_v1), ddof=1), np.std(np.array(results_v2), ddof=1)

    smoothness_v1 = np.mean(np.abs(np.diff(results_v1)))
    smoothness_v2 = np.mean(np.abs(np.diff(results_v2)))
    
    print(f'Дисперсия: {var1:.2f} | {var2:.2f}')
    print(f'Cтандартное отклонение: {std1:.2f} | {std2:.2f}')
    print(f'Гладкость: {smoothness_v1:.2f} | {smoothness_v2:.2f}\n')

        
