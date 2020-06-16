$TITLE CAMEROON COVERAGE MODEL
* Justin Kagin, June 2014

* The model reads in data from excel spreadsheet in the form of parameter distributions
* Then it uses them to make a coverage model for Cameroon

**(lgm): Be sure to use gamside. File>> New Proj >> "filename".gpr


* A few useful gams options
option limrow=30 ;
option limcol=30 ;
*(lgm): limrow controls the number of rows that are listed for each equation in the equation listing in the listing file.
*(lgm): limcol controls the number of columns that are listed for each variable in the column listing in the listing file.
*(lgm) What is the significance of 30? - limits the number of columns and rows, can play with this


$offlisting ;
* (lgm): control the listing output using $offlisting to suppress the echo print 
Sets
k interventions
j space
t time /1*10/
;
set t2(t) just the first 3 years /1, 2, 3 /
    t3(t) years 4 to 10 /4,5,6,7,8,9,10/
* choose the number of draws (ex: change the second number from dr11 to dr499)
* nb: must be greater than 10 to allow for percentiles to be computed
    draw /dr0*dr9/ ;
* (lgm): purpose of the draws? TBD - MonteCarlo


parameter
simplevacost(k,j,t)        Costs for iron from the simplified model
simplevabenefit(k,j,t)     Benefits for iron from the simplified model
;
* 1) Read in the data from all spreadsheets:
*--------------------------------------------------------------------------

* As a general rule, you should use one gdx file for each spreadsheet (keeps things clean)

* Input Simplified Model Costs for Iron
$call "gdxxrw input=Katie_VA_Benefits_and_Costs_1_8_2019.xlsx output=simplified_vacost.gdx index=Indexcost!A2"
*(lgm): GDXXRW is a utility to read and write Excel spreadsheet data. GDXXRW can read multiple ranges in a spreadsheet and write the data to a GDX file, or read from a GDX file, and write the data to different ranges in a spreadsheet.
*Is the entire "Katie_VA_Benefits_and_Costs_1_8_2019.xlsx" spreadsheet an input? Or are some of these sheets outputs?
$gdxin simplified_vacost.gdx
* (lgm): The $gdxin command is used in a sequence to load specified items from a GDX file 
$load k j SIMPLEVACOST
*(lgm) : ^^Is this a spreadsheet?
option simplevacost:3:1:1 ;
*(lgm):^^ Is this number of parameters?
display k, j, t, simplevacost ;

* Input Simplified Model Benefits for Iron
$call "gdxxrw input=Katie_VA_Benefits_and_Costs_1_8_2019.xlsx output=simplified_vabenefit.gdx index=Indexbenefit!A2"
$gdxin simplified_vabenefit.gdx
$load SIMPLEVABENEFIT
option simplevabenefit:3:1:1 ;
display simplevabenefit ;
*(lgm): no k, j, t sets for the benefits?; same questions as above also apply

Scalar
totalfunds1 total funds available /35821703/
totalbenefits total benefits available /13458058/
s loop value /1/
*(lgm): ^^ purpose of the s loop?
vawght      VA weight                                    /1/
alphakids   VA weight for children 6-59months            /1/
betawra     VA weight for benefits for WRA               /0/
zincwght    Zinc weight                                  /0/
zincwghtc    Zinc weight costs                           /0/
zinckidwght  Zinc weight for children 6-59 months        /0/
zincwrawght  Zinc weight for wra                         /0/
ironwght         Iron weight                             /0/
ironkidwght      Iron weight for children 6-59 months    /0/
ironwrawght     Iron weight for wra                      /0/
folatewght      Folate weight                            /0/
folatekidwght   Folate weight for children 6-59 months   /0/
folatewrawght   Folate weight for wra                    /0/
b12wght          B12 weight                              /0/
b12kidwght       B12 weight for children 6-59 months     /0/
b12wrawght       B12 weight for wra                      /0/
includecdti      1 if including intervention cdti        /0/
includehf        1 if including intervention hf          /0/
includedw        1 if including intervention dw          /0/
percben      Percentage of bau* benefits                 /1/
INTLEND      INTEREST RATE ON FUNDS LOANED OUT           /0/
INTLEND2     INTEREST RATE ON BENEFITS                  /0.03/;
*(lgm:)^ are most of these scalars binary? Allowing you to isolate each intervention? Can you look at multiple at once? --> yes, can select multiple at once, but lets just look at the VA one for now
*(lgm): X will be 0 or 1 (do it or not)


Parameter
DISCOUNT                 DISCOUNT FACTOR FOR BENEFITS
BETA(t)                  DISCOUNT MULTIPLIER FOR BENEFITS
DISCOUNT2                DISCOUNT FACTOR FOR COSTS
GAMMA(t)                 DISCOUNT MULTIPLIER FOR COSTS
totalfunds               TOTAL FUNDS AVAILABLE
totalbenefits2           TOTAL BENEFITS
totalbenefitsbau         TOTAL BENEFITS OF BAU*
ciron(k,j,t)             TOTAL COSTS IRON
covironwra(k,j,t)        COVERAGE MATRIX FOR IRON WRA
cva(k,j,t)                 TOTAL COSTS VA
covvakids(k,j,t)        COVERAGE MATRIX FOR VA CHILDREN
cov(k,j,t)               COVERAGE MATRIX
;

* Computing discount rates for costs and benefits (may differ if interest rates differ)
DISCOUNT    = 1/(1+INTLEND);
BETA(t)     = DISCOUNT**(ORD(t)-1) ;
DISCOUNT2    = 1/(1+INTLEND2);
GAMMA(t)     = DISCOUNT2**(ORD(t)-1) ;

* Defining constraint levels
totalfunds = totalfunds1*1;
*(lgm):^ Does the 1*1 keep it a scalar?

* Make the coverage and costs parameters
*covironwra(k,j,t)        = simpleironbenefit(k,j,t) ;
*ciron(k,j,t)             = simpleironcost(k,j,t) ;
covvakids(k,j,t)         = simplevabenefit(k,j,t) ;
cva(k,j,t)               = simplevacost(k,j,t) ;

*(lgm): Definitions for cov?; Why are covironwra and ciron greyed out?

* DEFINE SUBSETSS OF NATIONAL AND SUBNATIONAL INTERVENTIONS
*-------------------------------------------------------------------

set

* Vitamin A
 cubek(k) /cube, vascube, oilcube, cubemaize, vascubemaize, vasoilcube, oilcubemaize, vasoilcubemaize /

 oilk(k) /oil, vasoil, oilcube, oilmaize, vasoilmaize, vasoilcube, oilcubemaize, vasoilcubemaize /

 maizek(k) /maize, vasmaize, oilmaize, cubemaize, vascubemaize, vasoilmaize, oilcubemaize, vasoilcubemaize /
*(lgm): FYI, you have t choose maize for all 10 years and costs would start in year 1


* cubek(k) /cube, flourcube, cubeclinic, cubecomm, flourcubeclinic, flourcubecomm /

* flourk(k) /flour, flourcube, flourclinic, flourcomm, flourcubeclinic, flourcubecomm /
;
totalbenefitsbau=sum(t,GAMMA(t)*(sum((j),vawght*covvakids("vasoilold",j,t))));
totalbenefits2=percben*totalbenefitsbau ;
*(lgm): Difference in defining this as a set vs. parameter above? --> The bau is telling the optimization that the new selection must be at least the value of the BAU

covvakids("vasoilold",j,t)=0
*(lgm): so this is defining covvakids for the specific intervention (k = vasoiloid)

display totalbenefitsbau, totalbenefits2 ;

Variables
X(k,j,t)      QUANTITY OF VA INTERVENTION ZERO OR ONE
Y(k,j,t)      QUANTITY OF VA INTERVENTION ZERO OR ONE
*(lgm): ^Why are these zero or one, and what is x vs y
XCOST         TOTAL COST FOR X VARIABLE INTERVENTIONS
XCOV          TOTAL COVERAGE FOR X VARIABLE INTERVENTIONS
Z             TOTAL COSTS
BEN           TOTAL COVERAGE
YESCUBE(j,t)   equal to 1 if there is cube in j at t
YESOIL(j,t)    equal to 1 if there is oil in j at t
YESMAIZE(j,t)  equal to 1 if there is oil in j at t
*YESFLOUR(j,t)  equal to 1 if there is flour in j at t
*(lgm): Can these be set by the user, or are they determined by the optimization?
;

Binary Variable X, Y;

* this is useful to refer to two regions within a single equation
alias (j,jj) ;
alias (t,tt) ;
*(lgm): this sets a second name for the same set? Sort of, just the singular code just checks north=north, south=south,cities=cities. Now we can check south=south, south=north, and south=cities

Equations
benefit                  TOTAL AMOUNT OF COVERAGE BENEFITS
benefitconst             TOTAL AMOUNT OF PEOPLE THAT MUST BENEFIT IN TOTAL

*fundconst                THE TOTAL AMOUNT OF FUNDING
cost                     TOTAL COSTS FOR THE OPTIMAL INTERVENTIONS
onesx(j,t)               A CONSTRAINT ON THE NUMBER OF INTERVENTIONS THAT CAN BE CHOSEN FOR X VARIABLES INTERVENTIONS
onesy(j,t)               A CONSTRAINT ON THE NUMBER OF INTERVENTIONS THAT CAN BE CHOSEN FOR Y VARIABLES INTERVENTIONS
xcoveq(k,j,t)            THE AMOUNT OF COVERAGE FOR X
xcosteq(k,j,t)           THE AMOUNT OF COST FOR X
*(lgm): "ones" summarizes over all k interventions (x is the choice variable) - only 1 can be chosen in each space and time
*(lgm): FYI - there are 4 combinations and all the combinations of these as well
*(lgm): FYI - can't have oil and vasoil in the north


* Equations that force national interventions to be in all regions:
yescubeeq(j,t)       equation defining yescube>0 if there is cube in j
*yesfloureq(j,t)      equation defining yesflour>0 if there is flour in j
yesoileq(j,t)        equation defining yesoil>0 if there is oil in j
yesmaizeeq(j,t)      equation defining yesmaize>0 if there is maize in j
allcubeeq(j,jj,t)    equation forcing cube to be either 1 or 0 in all regions
*allfloureq(j,jj,t)   equation forcing flour to be either 1 or 0 in all regions
allmaizeeq(j,jj,t)   equation forcing maize to be either 1 or 0 in all regions
alloileq(j,jj,t)     equation forcing oil to be either 1 or 0 in all regions
*alloileq2(j,t,tt)     equation forcing oil to be either 1 or 0 in all regions
allmaizeeq2(j,t,tt)  equation forcing maize to be either 1 or 0 in all time periods
allcubeeq2(j,t,tt)  equation forcing cube to be either 1 or 0 in all time periods
*(lgm): Does this forcing occur through the optimization? Or it's selected by the user?

;

*tcovflour(oilk,j,t)=tcovflour(oilk,j,t)*1.002;

* Coverage and cost:
xcoveq(k,j,t) ..       XCOV(k,j,t)=e=vawght*covvakids(k,j,t)*x(k,j,t);
*(lgm): Amt of coverage is the weighting on VA (1)* the coverage matrix for children * qty of intervention (0 or 1, so this is binary?) --> yes, binary
*(lgm): What is e? --> e is equals, l is less than, g is greater than
xcosteq(k,j,t) ..      XCOST(k,j,t)=e=vawght*cva(k,j,t)*x(k,j,t);
* (lgm): Cost is the weighting on VA (1)* total cost of va * qty of intervention
benefit ..             BEN=e=sum(t,GAMMA(t)*(sum((k,j),XCOV(k,j,t))));
* (lgm): ".." notation? This is discounted benefits
cost ..                Z=e=sum(t,BETA(t)*(sum((k,j),XCOST(k,j,t)))) ;
* (lgm): ".." notation? This is discounted costs

* Constraints:
* Equity changes space
*benefitspace(j) ..          BENSPACE(j)=e=sum(t,GAMMA(t)*(sum((k),XCOV(k,j,t)))) ;
*benefitconstspace(j) ..     BENSPACE(j)=g=totalbenefitsbau2(j);

* Equity changes time
*benefittime(t) ..          BENTIME(t)=e=sum(j,GAMMA(t)*(sum((k),XCOV(k,j,t)))) ;
*benefitconsttime(t) ..     BENTIME(t)=g=totalbenefitsbau3(t);

* Equity changes space/time
*benefitspacetime(j,t) ..          BENSPACETIME(j,t)=e=GAMMA(t)*(sum((k),XCOV(k,j,t))) ;
*benefitconstspacetime(j,t) ..     BENSPACETIME(j,t)=g=totalbenefitsbau4(j,t);

benefitconst ..        BEN=g=totalbenefits2;
*(lgm): what is g? Why do we need to redefine this?
onesx(j,t)..           sum(k,x(k,j,t))=l=1;
onesy(j,t)..           sum(k,y(k,j,t))=l=1;
*(lgm): What is the purpose of the "ones" code?


* equations checking if there is maize, flour, oil and cube anywhere:
yescubeeq(j,t)..       yescube(j,t) =e= sum((cubek),x(cubek,j,t)) ;
*yesfloureq(j,t)..      yesflour(j,t) =e= sum((flourk),y(flourk,j,t)) ;
yesoileq(j,t)..        yesoil(j,t) =e= sum((oilk),x(oilk,j,t)) ;
yesmaizeeq(j,t)..      yesmaize(j,t) =e= sum((maizek),x(maizek,j,t)) ;

* equations forcing there to be maize, oil, or cube everywhere if it is anywhere:
allcubeeq(j,jj,t)..          yescube(j,t) =e= yescube(jj,t) ;
alloileq(j,jj,t)..           yesoil(j,t) =e= yesoil(jj,t) ;
allmaizeeq(j,jj,t)..         yesmaize(j,t) =e= yesmaize(jj,t) ;
*allfloureq(j,jj,t)..         yesflour(j,t) =e= yesflour(jj,t) ;
*(lgm): Why is the forcing needed?

* equations forcing there to be maize, in all times if it at anytime:
allmaizeeq2(j,t2,tt)..        yesmaize(j,tt) =e=yesmaize(j,t2) ;
allcubeeq2(j,t2,tt)..        yescube(j,tt) =e=yescube(j,t2) ;
*alloileq2(j,t2,tt)..        yesoil(j,tt) =e=yesoil(j,t2) ;
*(lgm): Again, why the forcing?

Model nutrition /all/ ;
option minlp=BONMIN ;
Solve nutrition using minlp minimizing z ;
Display  x.l, y.l, z.l, ben.l, xcov.l, xcost.l, totalfunds, totalbenefits;

Parameters
finalcov         Coverage per time period all
finalcost        Cost per time period
covbau           Coverage per time for BAU scenario
costbau          Cost per time for BAU scenario
tfinalcov        Total coverage for optimal model
tfinalcost       Total costs for optimal model
tcovbau          Total coverage for BAU
tcostbau         Total cost for BAU
costpw           Cost per woman of reproductive age for BAU scenario
costbaupw           Cost per woman of reproductive age
;
finalcov(t)              =sum(k,sum(j,xcov.l(k,j,t)))  ;
finalcost(t)             =sum(k,sum(j,xcost.l(k,j,t))) ;
covbau(t)                =sum(j,covvakids("vasoilold",j,t))  ;
costbau(t)               =sum(j,cva("vasoilold",j,t))  ;
costbaupw                =sum(t,costbau(t))/sum(t,covbau(t));
tfinalcov                =sum(t,finalcov(t));
tfinalcost               =sum(t,finalcost(t));
tcovbau                  =sum(t,covbau(t));
tcostbau                 =sum(t,costbau(t));
costpw                   =Z.l/BEN.l ;

display finalcov, finalcost, covbau, costbau, costbaupw, costpw;

* #################################################################################################
* ################################# OUTPUT THE TABLE WITH A PUT STATEMENT #########################
* #################################################################################################
* (This is useful to automate certain kinds of output and avoid repetitive excel manipulations
* It makes a text file (table1.txt) which can be easily cut and pasted into excel.

* OUTPUT: after the run, open the following .txt file.
* It can be cut+pasted to excel for easy comparison between runs
* (do a text-to-columns with semicolon as the separator)
file tablput20_4bk /table1.txt/;
put tablput20_4bk ;

* This is to have capital values in the denominator of the multipliers
put 'OPTIMIZED SCENARIO' /;

put 'Total cost and coverage by year' /;
loop(t,
     put t.tl 'cost';
     put  @45';' finalcost(t):12:0 /;
);
loop(t,
     put t.tl 'coverage';
     put  @45';' finalcov(t):12:0 /;
);
put //;

put 'Total cost and coverage by year for bau*' /;
loop(t,
     put t.tl 'cost';
     put  @45';' costbau(t):12:0 /;
);
loop(t,
     put t.tl 'coverage';
     put  @45';' covbau(t):12:0 /;
);
put //;

put 'Discounted total cost for BAU'/;
         put @45';' tcostbau:12:0 /;

put 'Discounted total benefits for BAU'/;
         put @45';' tcovbau:12:0 /;

put 'Discounted cost per woman of reproductive age for BAU'/;
         put @45';' costbaupw:6:2 /;

put 'Discounted total cost for optimal simulation'/;
         put @45';' tfinalcost:12:0 /;

put 'Discounted total benefits for optimal simulation'/;
         put @45';' tfinalcov:12:0 /;

put 'Discounted cost per woman of reproductive age for optimal simulation'/;
         put @45';' costpw:6:2 /;