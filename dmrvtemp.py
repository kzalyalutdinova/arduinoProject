import math

B = 3980.0
T0 = 298.15
R0 = 2000.0
M = 0.03995
P_ATM = 101325.0
R_GAS = 8.314

raw_data = [
    (3.618, 0.732), (3.643, 0.645), (3.599, 0.596), (3.55, 0.552),
    (3.521, 0.527), (3.579, 0.513), (3.511, 0.503), (3.574, 0.498),
    (3.54, 0.493), (3.506, 0.488), (3.545, 0.493), (3.555, 0.493),
    (3.55, 0.498), (3.496, 0.483), (3.486, 0.488)
]

def process_data(data):

    
    for i in range(1, len(data)):
        curr_flow_v, curr_temp_v = data[i]
        curr_flow = 38.75 * curr_flow_v ** 2   - 89.25 * curr_flow_v + 53.75 - 2.3;
        curr_temp_v = curr_temp_v * 2500 / (5 - curr_temp_v)
        curr_temp_k = 1.0 / (1.0/T0 + (1.0/B) * math.log(curr_temp_v / R0)) - 273;
        rho = (P_ATM * M) / (R_GAS * curr_temp_k)
        x = (curr_flow / rho)
        
        print(x)
       
output = process_data(raw_data)

