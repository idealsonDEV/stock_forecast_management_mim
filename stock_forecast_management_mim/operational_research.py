from __future__ import print_function
from ortools.linear_solver import pywraplp
#from ortools.sat.python import cp_model
from openerp.osv import osv, fields
import math

def op_solver(tonnage, data_raw):
    solver = pywraplp.Solver('Tonnage', pywraplp.Solver.GLOP_LINEAR_PROGRAMMING)
    #model = cp_model.CpModel()
    data = {}
    for item in data_raw:
    	data[item] = solver.IntVar(0, 4000, data_raw[item]['name'].encode('utf-8'))
        #data[item] = model.NewIntVar(0, 4000, data_raw[item]['name'].encode('utf-8'))


    #model.Add(sum([data[item] * data_raw[item]['weight']for item in data]) < tonnage)
    solver.Add(solver.Sum([data[item] * data_raw[item]['weight']for item in data]) <= (tonnage-1)) 
    #solver.Add(solver.Sum([data[item] * data_raw[item]['weight']for item in data]) >= tonnage-(tonnage/1000))

    for item in data_raw:
        if data_raw[item]['reste'] > data_raw[item]['ratio'] * (data_raw[516]['reste']+data_raw[516]['minimal']):
            solver.Add(data[item] == 0)
        else:
            ratio = data_raw[item]['ratio'] ## (((data_raw[516]['reste']+1)/data_raw[516]['minimal'])/((data_raw[item]['reste']+1)/data_raw[item]['minimal']))
            solver.Add(data[item] <= ratio * 1.1 * data[516])
            solver.Add(data[item] >= ratio * 0.9 * data[516])
        #model.Add(data[item] == data_raw[item]['ratio'] * data[516])


    #objective = solver.Objective()

    #objective.SetMinimization()
    solver.Maximize(solver.Sum([data[item] * data_raw[item]['weight']for item in data]))
    status = solver.Solve()
    #model.Maximize(sum([data[item] * data_raw[item]['weight']for item in data]))

    #lst = []
    poids = 0

    #solver = cp_model.CpSolver()
    #status = solver.Solve(model)

    # if status == cp_model.OPTIMAL:
    #     for item in data:
    #         data_raw[item]['optim'] = solver.Value(data[item])
    #         poids += data_raw[item]['optim'] * data_raw[item]['weight']
    #         if data_raw[item]['optim'] < 0.0:
    #             lst.append(item)
    #     #raise osv.except_osv("item",(poids,str(data_raw)))
    #     return poids, data_raw
    # else:
    #     raise osv.except_osv("Erreur","Optimisation non concluante")

    if status == pywraplp.Solver.OPTIMAL:
    	for item in data:
    		data_raw[item]['optim'] = math.floor(data[item].solution_value())
    		poids += data_raw[item]['optim'] * data_raw[item]['weight']
    		if data_raw[item]['optim'] < 0.0:
    			lst.append(item)
    	return poids, data_raw
    else:
        raise osv.except_osv("Erreur","Optimisation non concluante")
