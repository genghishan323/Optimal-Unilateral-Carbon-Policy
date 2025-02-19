import math
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.optimize import fsolve
from scipy.integrate import quad

## Comsumes:
## p (a vector of price and tax), varphi (social cost of carbon), tax_scenario,
## ParaList (a list of params for tuning the model) and df

## Returns:
## the sum of absolute value differences of total extraction - consumption
## and the difference between tb (border adjustment) and it's equilibrium condition in paper.
def objective(p, varphi, tax_scenario, ParaList, df):
    pe = p[0]
    tb_mat = p[1:]
    alpha, theta, sigma, sigmastar, epsilonD,epsilonDstar, epsilonS, epsilonSstar, beta, gamma, logit = ParaList
    
    if tax_scenario['tax_sce']!='Unilateral':
        print("shouldn't be here")
        return 0

    ## compute jbar_hat and jbar_prime values
    jxbar_hat, j0_hat, jmbar_hat, jxbar_prime, jmbar_prime, j0_prime = jbar_hat(pe, alpha, theta, tb_mat, df)
    
    #if te is too large, Home stop producing
    petbte = pe + tb_mat[0] - varphi
    if (petbte < 0):
        petbte = 0

    ## compute equilibrium energy extraction
    Qe_prime, Qestar_prime = compute_qe(petbte, epsilonS, epsilonSstar, logit, beta, gamma, pe, df)

    ## compute equilibrium energy consumption
    CeHH_prime, CeFH1_prime, CeFH2_prime, CeFH_prime, CeHF_prime, CeFF_prime = compute_ce(pe, tb_mat, epsilonD,j0_hat, j0_prime, jmbar_hat, jxbar_prime, alpha, sigma, theta, epsilonDstar,sigmastar, df)
    
    ## compute one term of value of exports (I think)
    VgFH2_prime = compute_vg(df, pe, alpha, sigmastar, theta, epsilonDstar, jxbar_prime, j0_prime)
    
    ## compute difference of extraction and consumption
    diff = Qe_prime + Qestar_prime - (CeHH_prime + CeFH_prime + CeHF_prime + CeFF_prime)
    
    ## compute second equilibrium condition
    pai_g = (pe + tb_mat[0]) * CeFH2_prime / (1 - alpha) - VgFH2_prime
    numerator = varphi * epsilonSstar * Qestar_prime - sigmastar * (1-alpha) * pai_g
    denominator = epsilonSstar * Qestar_prime + epsilonDstar * CeFF_prime
    diff1 = tb_mat[0] * denominator - numerator
        
    return abs(diff) + abs(diff1)


## computes j values
def jbar_hat(pe, alpha, theta, tb_mat, df):
    jxbar_hat = (pe**(-alpha*theta) * (pe+tb_mat[0])**(-(1-alpha)*theta) / 
                 (df['jxbar'] * pe**(-alpha*theta) * (pe+tb_mat[0])**(-(1-alpha)*theta) + 
                  (1-df['jxbar']) * (pe + (1-alpha) * tb_mat[0])**(-theta)))
    
    j0_hat = (pe+tb_mat[0])**(-(1-alpha)*theta) / (df['jxbar'] * (pe+tb_mat[0])**(-(1-alpha)*theta) + (1-df['jxbar']) * pe**(-(1-alpha)*theta))
    
    jmbar_hat = 1
    
    ## compute final values for j's
    jxbar_prime = jxbar_hat * df['jxbar']
    jmbar_prime = jmbar_hat * df['jmbar']
    j0_prime = j0_hat * df['jxbar']
    
    return (jxbar_hat, j0_hat, jmbar_hat, jxbar_prime, jmbar_prime, j0_prime)

def integrand(i, theta, sigmastar):
    return (i ** ((1 + theta) / theta - 1) * (1 - i) ** ((theta - sigmastar) / theta - 1)) 

def incomp_beta(low, hi, theta, sigmastar):
    return quad(integrand,low, hi, args=(theta, sigmastar))[0]

## computes extraction values (home, foreign)
def compute_qe(petbte, epsilonS, epsilonSstar, logit, beta, gamma, pe, df):
    if logit==1:
        epsilonS=beta*(1-gamma)/(1-gamma+gamma*petbte**beta)
        epsilonSstar=beta*(1-gamma)/(1-gamma+gamma*pe**beta)
        Qe_hat = (petbte)**beta/(1-gamma+gamma*(petbte)**beta)
        Qestar_hat = pe**beta/(1-gamma+gamma*pe**beta)
        
    ## compute hat values    
    Qe_hat = (petbte) ** epsilonS
    Qestar_hat = pe ** epsilonSstar
    
    ## compute final values
    Qe_prime = df['Qe'] * Qe_hat
    Qestar_prime = df['Qestar'] * Qestar_hat
    
    return (Qe_prime, Qestar_prime)

## computes consumption values (home, import, export, foreign)
def compute_ce(pe, tb_mat, epsilonD,j0_hat, j0_prime, jmbar_hat, jxbar_prime, alpha, sigma, theta, epsilonDstar, sigmastar, df):
    
    ## home produce for home use
    CeHH_hat = (pe + tb_mat[0]) ** (-epsilonD) * jmbar_hat ** (1 + (1 - sigma)/theta)
    CeHH_prime = df['CeHH'] * CeHH_hat
    
    ## compute incomplete beta values
    Bfunvec1_prime = incomp_beta(0, j0_prime, theta, sigmastar)
    Bfunvec2_prime = incomp_beta(0, jxbar_prime, theta, sigmastar)
    
    CeFH1_hat = (pe +tb_mat[0])**(-epsilonDstar) * j0_hat**(1 + (1 - sigmastar)/theta)
    CeFH2_hat = ((1 + (1 - sigmastar)/theta) * 
                 ((1-df['jxbar'])/df['jxbar'])**(sigmastar/theta) * 
                 pe**(-epsilonDstar) * (1 + tb_mat[0]/pe)**(-alpha) * 
                 (Bfunvec2_prime - Bfunvec1_prime) /
                 df['jxbar']**(1+(1-sigmastar)/theta))
    
    CeFH1_prime = df['CeFH'] * CeFH1_hat
    CeFH2_prime = df['CeFH'] * CeFH2_hat
    CeFH_hat = CeFH1_hat + CeFH2_hat
    
    if np.isnan(CeFH_hat):
        CeFH_hat=0
        
    CeFH_prime =df['CeFH'] * CeFH_hat
    
    CeHF_hat = (pe + tb_mat[0]) ** (-epsilonD)
    CeHF_prime = df['CeHF'] * CeHF_hat
    
    CeFF_prime = df['CeFF'] * ((1 - jxbar_prime)/(1-df['jxbar'])) ** (1 + (1 - sigmastar)/theta) * pe ** (-epsilonDstar)
    
    return (CeHH_prime, CeFH1_prime, CeFH2_prime, CeFH_prime, CeHF_prime, CeFF_prime)
    

def compute_vg(df, pe, alpha, sigmastar, theta, epsilonDstar, jxbar_prime, j0_prime):
    VgFH = df['CeFH'] /(1 - alpha)
    VgFH2_hat = (pe**(1 - epsilonDstar) * ((1-j0_prime)**(1+(1-sigmastar)/theta) - (1-jxbar_prime)**(1+(1-sigmastar)/theta)) / 
                 (df['jxbar']  * (1 - df['jxbar'] )**( (1-sigmastar)/theta)))
    VgFH2_prime = VgFH * VgFH2_hat
    
    return VgFH2_prime


## returns equilibrium tb and pe as a df
def assign_eq(df, prevtb, prevpe, varphi, ParaList, tax_scenario):
    region = df['region_scenario']
    if type(prevtb) != int:
        #print(prevtb)
        #print(prevtb[prevtb['region'] == region])
        prevtb = prevtb[prevtb['region'] == region]['tb']
        prevpe = prevpe[prevpe['region'] == region]['pe']
        
    prevpe, prevtb = find_opt(prevpe, prevtb, varphi, tax_scenario, ParaList, df, region)
        
    return pd.Series({'pe': prevpe, 'tb': prevtb, 'region': region})

# program to grid search optimal starting point to find equilibrium tax and price, if no statement printed then equilibrium price is found
# returns the tuple of equilibrium price and tax, if no equilibrium found, return the previous tb and pe
def find_opt(prevpe, prevtb, varphi, tax_scenario, ParaList, df, region):
    retpe = -1
    rettb = -1
    threshold = 0.01
    # grid search for pe, since the objective is unstable in pe space
    for pe in np.append(prevpe, np.arange(0,3,0.1)):
        res1 = minimize(objective, (pe, prevtb), args = (varphi, tax_scenario, ParaList, df), bounds = [(0,np.inf), (0, np.inf)], method = 'Nelder-Mead', options = {'maxfev': 100000})
        diff = verify([res1.x[1]], res1.x[0], varphi, tax_scenario, ParaList, df)
        if (diff[0] < threshold and diff[1] < threshold):
            retpe = res1.x[0]
            rettb = res1.x[1]
            #print(diff)
            break
    if (retpe == -1):
        print('no result found, returning placeholder (previous value)', varphi, region)
        retpe = 0.1
        rettb = 0.1
    return (retpe, rettb)


# verify, given tax and pe, whether they satisfy the two equations in paper
def verify(tb_mat, pe, varphi, tax_scenario, ParaList, df):
    alpha, theta, sigma, sigmastar, epsilonD,epsilonDstar, epsilonS, epsilonSstar, beta, gamma, logit = ParaList
    
    if tax_scenario['tax_sce']!='Unilateral':
        print("shouldn't be here")
        return 0

    ## compute jbar_hat and jbar_prime values
    jxbar_hat, j0_hat, jmbar_hat, jxbar_prime, jmbar_prime, j0_prime = jbar_hat(pe, alpha, theta, tb_mat, df)
    
    #if te is too large, Home stop producing
    petbte = pe + tb_mat[0] - varphi
    if (petbte < 0):
        petbte = 0

    ## compute equilibrium energy extraction
    Qe_prime, Qestar_prime = compute_qe(petbte, epsilonS, epsilonSstar, logit, beta, gamma, pe, df)

    ## compute equilibrium energy consumption
    CeHH_prime, CeFH1_prime, CeFH2_prime, CeFH_prime, CeHF_prime, CeFF_prime = compute_ce(pe, tb_mat, epsilonD,j0_hat, j0_prime, jmbar_hat, jxbar_prime, alpha, sigma, theta, epsilonDstar,sigmastar, df)
    
    ## compute one term of value of exports (I think)
    VgFH2_prime = compute_vg(df, pe, alpha, sigmastar, theta, epsilonDstar, jxbar_prime, j0_prime)
    
    ## compute difference of extraction and consumption
    diff = Qe_prime + Qestar_prime - (CeHH_prime + CeFH_prime + CeHF_prime + CeFF_prime)
    
    ## compute second equilibrium condition
    pai_g = (pe + tb_mat[0]) * CeFH2_prime / (1 - alpha) - VgFH2_prime
    numerator = varphi * epsilonSstar * Qestar_prime - sigmastar * (1-alpha) * pai_g
    denominator = epsilonSstar * Qestar_prime + epsilonDstar * CeFF_prime
    diff1 = tb_mat[0] * denominator - numerator
        
    return (abs(diff), abs(diff1))


## same functionality as above except computes all other values of interest given optimal pe and tb
def compute_all(df, varphi, tax_scenario, ParaList):
    
    pe= df['pe']
    # print('pe='+str(pe))
    alpha, theta, sigma, sigmastar, epsilonD,epsilonDstar, epsilonS, epsilonSstar, beta, gamma, logit = ParaList
    
   ## optimal values
    # jxbar_hat =   (1 - df['jxbar']) ** (-1) / (((1 - df['jxbar']) ** (-1) - 1) + (1 + (1 - alpha) * df['tb']/pe) ** (-theta) * (1 + df['tb']/pe) ** ((1 - alpha) * theta));
    jxbar_hat = pe**(-alpha*theta) * (pe+df['tb'])**(-(1-alpha)*theta) / ( df['jxbar'] * pe**(-alpha*theta) * (pe+df['tb'])**(-(1-alpha)*theta) + (1-df['jxbar']) * (pe + (1-alpha) * df['tb'])**(-theta));
    j0_hat = (pe+df['tb'])**(-(1-alpha)*theta) / (df['jxbar'] * (pe+df['tb'])**(-(1-alpha)*theta) + (1-df['jxbar']) * pe**(-(1-alpha)*theta) );
    jmbar_hat = 1 ;
    

    df['te']=varphi;
    df['prop']=1;
        
    jxbar_prime = jxbar_hat * df['jxbar'];
    jmbar_prime = jmbar_hat * df['jmbar'];
    j0_prime = j0_hat * df['jxbar'];

    def tempFunction(i, theta, sigmastar):
        return (i ** ((1 + theta) / theta - 1) * (1 - i) ** ((theta - sigmastar) / theta - 1)) 
    
    Bfunvec1_prime = quad(tempFunction,0,j0_prime, args=(theta, sigmastar))[0];
    Bfunvec2_prime = quad(tempFunction,0,jxbar_prime, args=(theta, sigmastar))[0];

    #if te is too large, HoGe stop producing
    petbte = pe + df['tb'] - df['te'];
    z = pe +  df['tb'] >= df['te'];

    petbte = petbte * z;

    Qe_hat = (petbte) ** epsilonS;
    Qestar_hat = pe ** epsilonSstar;
          
    if logit==1:
        epsilonS=beta*(1-gamma)/(1-gamma+gamma*petbte**beta);
        epsilonSstar=beta*(1-gamma)/(1-gamma+gamma*pe**beta);
        Qe_hat = (petbte)**beta/(1-gamma+gamma*(petbte)**beta);
        Qestar_hat = pe**beta/(1-gamma+gamma*pe**beta);
 
    Qe_prime = df['Qe'] * Qe_hat;
    Qestar_prime = df['Qestar'] * Qestar_hat;
    
    
    CeHH_hat = (pe + df['tb']) ** (-epsilonD) * jmbar_hat ** (1 + (1 - sigma)/theta);
    CeHH_prime = df['CeHH'] * CeHH_hat;
       
    
    # CeFH_hat = (1 + (1 - sigmastar)/theta) * pe ** (-(1 - alpha) * sigmastar) * (pe + df['tb']) ** (-alpha) * Bfunvec_prime/(df['jxbar'] ** (1 +1/theta)) * (1 - df['jxbar']) ** (sigmastar/theta);
    CeFH1_hat = (pe +df['tb'])**(-epsilonDstar) * j0_hat**(1 + (1 - sigmastar)/theta);
    CeFH2_hat = (1 + (1 - sigmastar)/theta) * ((1-df['jxbar'])/df['jxbar'])**(sigmastar/theta) * pe**(-epsilonDstar) * (1 + df['tb']/pe)**(-alpha) * (Bfunvec2_prime - Bfunvec1_prime)/df['jxbar']**(1+(1-sigmastar)/theta);
    CeFH1_prime = df['CeFH'] * CeFH1_hat;
    CeFH2_prime = df['CeFH'] * CeFH2_hat;
    CeFH_hat = CeFH1_hat + CeFH2_hat;
    
    if np.isnan(CeFH_hat)==True:
        CeFH_hat=0
    CeFH_prime =df['CeFH'] * CeFH_hat;
    
    
    CeHF_hat = (pe + df['tb']) ** (-epsilonD);
    
    CeHF_prime = df['CeHF'] * CeHF_hat;
    
    CeFF_prime = df['CeFF'] * ((1 - jxbar_prime)/(1-df['jxbar'])) ** (1 + (1 - sigmastar)/theta) * pe ** (-epsilonDstar);
    
    ##
    VgHH = df['CeHH']/(1 - alpha);
    VgFF = df['CeFF']/(1 - alpha);
    
    VgFH = df['CeFH'] /(1 - alpha);
    # VgFH_prime = VgFH * pe ** ((1 - sigmastar) * (1 - alpha)) * (1 - (1 - jxbar_prime) ** (1 + (1 - sigmastar)/theta))/ (df['jxbar'] * (1 - df['jxbar']) ** ( (1-sigmastar)/theta));
    VgFH1_hat = (pe + df['tb']) * CeFH1_hat;
    VgFH2_hat = pe**(1 - epsilonDstar) * ((1-j0_prime)**(1+(1-sigmastar)/theta) - (1-jxbar_prime)**(1+(1-sigmastar)/theta))/ (df['jxbar']  * (1 - df['jxbar'] )**( (1-sigmastar)/theta));
    VgFH1_prime = VgFH * VgFH1_hat;
    VgFH2_prime = VgFH * VgFH2_hat;
    VgFH_hat = VgFH1_hat + VgFH2_hat;
    if np.isnan(VgFH_hat)==True:
            VgFH_hat=0
    VgFH_prime = VgFH * VgFH_hat;  

    VgHF = df['CeHF']/(1 - alpha);
    VgHF_hat = (pe + alpha * df['tb']) * CeHF_hat;
    VgHF_prime = VgHF * VgHF_hat;
    
    Ge_prime = CeHH_prime + CeFH_prime;
    Ge_hat = Ge_prime/df['Ge'];
    Gestar_prime = CeFF_prime + CeHF_prime;
    
    Ce_prime = CeHH_prime + CeHF_prime;
    Ce_hat = Ce_prime/df['Ce'];
    Cestar_prime = CeFF_prime + CeFH_prime;
    
    Xe = df['Qe'] - df['Ge'];
    Xe_prime = Qe_prime - Ge_prime;
    Xg = VgFH - VgHF;
    Xg_prime = VgFH_prime - VgHF_prime;
    
    Xestar_prime = Qestar_prime - Gestar_prime;
    Qeworld_prime=Qe_prime+Qestar_prime;
    Geworld_prime=CeHH_prime+CeFH_prime+CeHF_prime+CeFF_prime;
    
    pai_g = VgFH - (pe + df['tb']) * df['CeFH'] / (1 - alpha);
    subsidy_ratio = (df['tb']/pe * (1 - alpha)) / (1 + df['tb']/pe * (1 - alpha));
    
    Ve_prime=(pe+df['tb']) * Ce_prime;
    
    Vestar_prime= (pe+df['tb']) * CeFH_prime  + pe * CeFF_prime;
    Vestar_prime= (pe+df['tb']) * CeFH1_prime + pe * CeFH2_prime + pe * CeFF_prime;
    
    Vg = df['Ce'] /(1-alpha)
    Vg_prime_hat = (pe + df['tb']) ** (1-epsilonD)
    Vg_prime = Vg * Vg_prime_hat
    #print(pe + df['tb'], Vg_prime)
    
    Vgstar = df['Cestar'] /(1-alpha)
    Vgstar_prime = VgFH_prime + CeFF_prime/(1-alpha)* pe
    #print(Vgstar_prime, 'first')
    Vgstar_hat = ((df['jxbar'] / j0_prime) * (pe + df['tb'])**(-(1-alpha) * theta)) ** (-(1-sigmastar) / theta)
    Vgstar_prime = Vgstar_hat * Vgstar
    
    #print(Vgstar_prime, 'second')
    
    Lg = alpha/(1-alpha) * df['Ge'];
    Lg_prime = alpha/(1-alpha) * (pe + df['tb']) * Ge_prime;
   
    
    Lgstar = alpha/(1-alpha) * df['Gestar'];
    Lgstar_prime = alpha/(1-alpha) * (pe+df['tb']) * CeHF_prime +alpha/(1-alpha) * pe * CeFF_prime;


    delta_Le = (epsilonS/(epsilonS + 1)) * df['Qe'] * (petbte**(epsilonS + 1) - 1);
    delta_Lestar = (epsilonSstar/(epsilonSstar + 1)) * df['Qestar'] * (pe**(epsilonSstar + 1) - 1);
    
    def Func(a, beta, gamma):
        return (((1-gamma)*a**beta)/(1-gamma+gamma*a**beta)**2)
    if logit==1:
        delta_Le = beta * df['Qe'] * quad(Func,1,petbte, args=(beta, gamma))[0];
        delta_Lestar = beta * df['Qestar'] * quad(Func,1,pe, args=(beta, gamma))[0];
    
    leakage1 = -(Qestar_prime - df['Qestar'])/(Qeworld_prime - df['Qeworld']);
    leakage2 = -(Gestar_prime - df['Gestar'])/(Qeworld_prime - df['Qeworld']);
    leakage3 = -(Cestar_prime - df['Cestar'])/(Qeworld_prime - df['Qeworld']);   
    chg_extraction=Qestar_prime-df['Qestar'];
    chg_production=Gestar_prime-df['Gestar'];
    chg_consumption=Cestar_prime-df['Cestar'];
    chg_Qeworld=Qeworld_prime-df['Qeworld'];

       
    delta_U = -delta_Le - delta_Lestar - (Lg_prime - Lg) - (Lgstar_prime - Lgstar) \
           + Vg * (alpha - 1) * math.log(pe + df['tb']) + Vgstar * (1/theta) * math.log(df['jxbar']/j0_prime * (pe+df['tb'])**(-(1-alpha)*theta)) \
           - varphi * (Qeworld_prime - df['Qeworld']);
    if pe<0:
        pe=0.0001
    
    
    welfare = delta_U/Vg*100;  
    welfare_noexternality = (delta_U + varphi * (Qeworld_prime - df['Qeworld']) )/Vg*100;  
    
    return(pd.Series({ 'varphi': varphi, 'jxbar_prime': jxbar_prime, 'jmbar_prime': jmbar_prime, 'j0_prime': j0_prime, \
                      'Qe_prime': Qe_prime, 'Qestar_prime': Qestar_prime, 'Qeworld_prime': Qeworld_prime, \
                      'CeHH_prime': CeHH_prime,'CeFH_prime': CeFH_prime, 'CeHF_prime': CeHF_prime, 'CeFF_prime': CeFF_prime,\
                      'Ge_prime': Ge_prime,'Ce_prime': Ce_prime, 'Gestar_prime': Gestar_prime,'Cestar_prime': Cestar_prime, \
                      'VgFH_prime': VgFH_prime, 'VgHF_prime': VgHF_prime, \
                      'VgFH1_prime': VgFH1_prime, 'VgFH2_prime': VgFH2_prime, \
                      'CeFH1_prime': CeFH1_prime, 'CeFH2_prime': CeFH2_prime, \
                      'Vg_prime': Vg_prime, 'Vgstar_prime': Vgstar_prime, \
                      'Lg_prime': Lg_prime, 'Lgstar_prime': Lgstar_prime, \
                      'Ve_prime': Ve_prime, 'Vestar_prime': Vestar_prime, \
                      'delta_Le': delta_Le, 'delta_Lestar': delta_Lestar, \
                      'leakage1': leakage1, 'leakage2': leakage2,'leakage3': leakage3, \
                      'leakage3': leakage3, 'chg_extraction': chg_extraction, 'chg_production': chg_production, \
                      'chg_consumption': chg_consumption,'chg_Qeworld':chg_Qeworld, 'pai_g': pai_g, \
                      'subsidy_ratio': subsidy_ratio, 'welfare':welfare, 'welfare_noexternality':welfare_noexternality}))