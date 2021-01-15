# -*- coding: utf-8 -*-
# vim: tabstop=4 shiftwidth=4 softtabstop=4
#
# Copyright (C) 2014-2021 GEM Foundation
#
# OpenQuake is free software: you can redistribute it and/or modify it
# under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# OpenQuake is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with OpenQuake. If not, see <http://www.gnu.org/licenses/>.

"""
Module exports :class:`KothaEtAl2016`,
               :class:`KothaEtAl2016Italy`,
               :class:`KothaEtAl2016Turkey`,
               :class:`KothaEtAl2016Others`,
"""
import numpy as np

from scipy.constants import g

from openquake.hazardlib.gsim.base import GMPE, CoeffsTable
from openquake.hazardlib import const
from openquake.hazardlib.imt import PGA, PGV, SA


class KothaEtAl2016(GMPE):
    """
    Implements unregionalised form of the European GMPE of:
    Kotha, S. R., Bindi, D. and Cotton, F. (2016) "Partially non-ergodic
    region specific GMPE for Europe and the Middle-East", Bull. Earthquake Eng.
    14: 1245 - 1263
    """
    #: Supported tectonic region type is 'active shallow crust'
    DEFINED_FOR_TECTONIC_REGION_TYPE = const.TRT.ACTIVE_SHALLOW_CRUST

    #: Set of :mod:`intensity measure types <openquake.hazardlib.imt>`
    #: this GSIM can calculate. A set should contain classes from module
    #: :mod:`openquake.hazardlib.imt`.
    DEFINED_FOR_INTENSITY_MEASURE_TYPES = set([
        PGA,
        PGV,
        SA
    ])

    #: Supported intensity measure component is the geometric mean of two
    #: horizontal components
    DEFINED_FOR_INTENSITY_MEASURE_COMPONENT = const.IMC.AVERAGE_HORIZONTAL

    #: Supported standard deviation types are inter-event, intra-event
    #: and total
    DEFINED_FOR_STANDARD_DEVIATION_TYPES = set([
        const.StdDev.TOTAL,
        const.StdDev.INTER_EVENT,
        const.StdDev.INTRA_EVENT
    ])

    #: Required site parameter is only Vs30
    REQUIRES_SITES_PARAMETERS = {'vs30'}

    #: Required rupture parameters are magnitude only (eq. 1).
    REQUIRES_RUPTURE_PARAMETERS = {'mag'}

    #: Required distance measure is Rjb (eq. 1).
    REQUIRES_DISTANCES = {'rjb'}

    def get_mean_and_stddevs(self, sites, rup, dists, imt, stddev_types):
        """
        See :meth:`superclass method
        <.base.GroundShakingIntensityModel.get_mean_and_stddevs>`
        for spec of input and result values.
        """
        # extracting dictionary of coefficients specific to required
        # intensity measure type.

        C = self.COEFFS[imt]

        mean = (self._get_magnitude_term(C, rup.mag) +
                self._get_distance_term(C, dists.rjb, rup.mag) +
                self._get_site_term(C, sites.vs30))

        # Units of GMPE are in terms of m/s (corrected in an Erratum)
        # Convert to g
        if imt.name in "SA PGA":
            mean = np.log(np.exp(mean) / g)
        else:
            # For PGV convert from m/s to cm/s/s
            mean = np.log(np.exp(mean) * 100.)

        # Get standard deviations
        stddevs = self._get_stddevs(C, stddev_types, dists.rjb.shape)
        return mean, stddevs

    def _get_magnitude_term(self, C, mag):
        """
        Returns the magnitude scaling term - equation 3
        """
        if mag >= self.CONSTS["Mh"]:
            return C["e1"] + C["b3"] * (mag - self.CONSTS["Mh"])
        else:
            return C["e1"] + (C["b1"] * (mag - self.CONSTS["Mh"])) +\
                (C["b2"] * (mag - self.CONSTS["Mh"]) ** 2.)

    def _get_distance_term(self, C, rjb, mag):
        """
        Returns the general distance scaling term - equation 2
        """
        c_3 = self._get_anelastic_coeff(C)
        rval = np.sqrt(rjb ** 2. + C["h"] ** 2.)
        return (C["c1"] + C["c2"] * (mag - self.CONSTS["Mref"])) *\
            np.log(rval / self.CONSTS["Rref"]) +\
            c_3 * (rval - self.CONSTS["Rref"])

    def _get_anelastic_coeff(self, C):
        """
        This function is a regionalisable parameter - will be modified in
        other classes
        """
        return C["c3"]

    def _get_site_term(self, C, vs30):
        """
        Returns only a linear site amplification term
        """
        dg1, dg2 = self._get_regional_site_term(C)
        return (C["g1"] + dg1) + (C["g2"] + dg2) * np.log(vs30)

    def _get_regional_site_term(self, C):
        """
        Region specific site term - modified in subclasses
        """
        return 0., 0.

    def _get_stddevs(self, C, stddev_types, stddev_shape):
        """
        Returns a total standard deviation
        Intra-event standard deviation should be treated here as
        sqrt(phi0 ** 2. + phiS2S ** 2.)
        """
        stddevs = []
        for stddev_type in stddev_types:
            assert stddev_type in self.DEFINED_FOR_STANDARD_DEVIATION_TYPES
            if stddev_type == const.StdDev.TOTAL:
                stddevs.append(C['sigma'] + np.zeros(stddev_shape))
            elif stddev_type == const.StdDev.INTRA_EVENT:
                phi = np.sqrt(C['phi0'] ** 2. + C["phiS2S"] ** 2.)
                stddevs.append(phi + np.zeros(stddev_shape))
            elif stddev_type == const.StdDev.INTER_EVENT:
                stddevs.append(C['tau'] + np.zeros(stddev_shape))
        return stddevs

    COEFFS = CoeffsTable(sa_damping=5, table="""
    imt                   e1                  b1                    b2                    b3                   c1                  c2                       c3                  h             g1              g2                 tau                phi0               sigma         phiS2S               sigma           Dc3IT         Dc3OTH                     Dc3TR      SE(Dc3IT)     SE(Dc3OTH)      SE(Dc3TR)         tau_c3           Dg1IT          Dg1OTH          Dg1TR          Dg2IT         Dg2OTH           Dg2TR      SE(Dg2IT)     SE(Dg2OTH)      SE(Dg2TR)      SE(Dg1IT)     SE(Dg1OTH)      SE(Dg1TR)         tau_g1         tau_g2
    pgv    0.773448532300000    0.48295609180000   -0.1013899388000000   -0.0211759777000000   -1.197557080000000   0.229140238700000   -0.0000830116515161252   5.84530471620000   2.1875716805   -0.3643741495   0.348763395300000   0.495980939200000   0.768173253600000   0.3137247297   0.682683091907392   -0.0018916416   0.0014236266    0.00050081190000000000   0.0007689578   0.0007372030   0.0003534052   0.0015388227   -0.2959264052   -1.0821939285   1.3782664393   0.0507702961   0.1856654408   -0.2364608034   0.0491199945   0.0393998898   0.0598580222   0.2863072456   0.2296513693   0.3488963189   1.0673423315   0.1831174421
    pga    2.981853543700000   -0.36324783770000   -0.1947968611000000   -0.4057967936000000   -1.230785202700000   0.271868892300000   -0.0039450559000000000   6.38988189290000   1.4069433075   -0.2342417112   0.349815625100000   0.450631096100000   0.723682628400000   0.3304253082   0.659257340221143   -0.0032597832   0.0032648044   -0.00000439588422080639   0.0007949687   0.0007572335   0.0003354350   0.0027446152   -0.3602648470   -0.6776115954   1.0380588295   0.0632138563   0.1188970925   -0.1821429513   0.0453351292   0.0371438274   0.0550867309   0.2583714144   0.2116880096   0.3139471920   0.7911010240   0.1388105096
    0.01   3.002028294200000   -0.36603926960000   -0.1933119745000000   -0.4119542683000000   -1.235690007800000   0.271682730700000   -0.0038461541000000000   6.42510376690000   1.3986480324   -0.2328051104   0.347165581200000   0.452282136000000   0.723328345000000   0.3303191705   0.658933855340932   -0.0033370251   0.0034089753   -0.00007218609764977390   0.0007973964   0.0007591361   0.0003359461   0.0028333710   -0.3506434045   -0.6627804988   1.0133951420   0.0616159653   0.1164655026   -0.1780764139   0.0449108580   0.0368500864   0.0544677112   0.2555781783   0.2097060349   0.3099642047   0.7735091224   0.1359230224
    0.02   3.063886757900000   -0.36766026720000   -0.1924547062000000   -0.4254010617000000   -1.250786612600000   0.272735132100000   -0.0037520606000000000   6.33634383160000   1.3823143357   -0.2300559740   0.350503318700000   0.454352863500000   0.727649531600000   0.3321209893   0.663018440561026   -0.0034295045   0.0034948203   -0.00006496111175672410   0.0008030409   0.0007645627   0.0003378673   0.0029052359   -0.3794085084   -0.6551011990   1.0344459042   0.0668475713   0.1154215664   -0.1822578963   0.0446512509   0.0366716719   0.0540808095   0.2534282729   0.2081383681   0.3069478650   0.7842928661   0.1381837051
    0.03   3.128272124600000   -0.37766990480000   -0.1828190988000000   -0.4404575362000000   -1.267446341900000   0.277810808500000   -0.0037139223000000000   6.10844028110000   1.3123984433   -0.2184227802   0.348022252800000   0.461449929300000   0.733244620400000   0.3358990123   0.668493584231799   -0.0035636966   0.0036420721   -0.00007836964492686870   0.0008121313   0.0007726011   0.0003414672   0.0030158759   -0.3760026560   -0.6518269885   1.0284122276   0.0664490638   0.1151941186   -0.1817461394   0.0444499669   0.0365805780   0.0536542632   0.2515205628   0.2069915533   0.3036031596   0.7793626014   0.1377328466
    0.04   3.222582777700000   -0.41376738240000   -0.1677810024000000   -0.4870244514000000   -1.298602166200000   0.290559314500000   -0.0037685605000000000   6.09639971500000   1.2438501532   -0.2070306129   0.350246760300000   0.462720624500000   0.737868184500000   0.3420262907   0.673620926759492   -0.0037184552   0.0037076830    0.00001077989698630680   0.0008179932   0.0007779008   0.0003431692   0.0031051599   -0.4086767835   -0.6061297199   1.0141156623   0.0722579789   0.1071695538   -0.1793053854   0.0449985578   0.0370833760   0.0542035116   0.2545029094   0.2097362128   0.3065643009   0.7672503000   0.1356572192
    0.05   3.304178248500000   -0.47788152330000   -0.1649466600000000   -0.4971193313000000   -1.321405889500000   0.300993708300000   -0.0038844433000000000   6.08554732440000   1.1628198018   -0.1935756212   0.352007488000000   0.469497842200000   0.747156032600000   0.3500096696   0.683260026821434   -0.0037426325   0.0037770187   -0.00004936490788013450   0.0008286535   0.0007876888   0.0003476605   0.0031459981   -0.4388084783   -0.5624400618   1.0013027801   0.0776274032   0.0994984454   -0.1771354439   0.0457485413   0.0377599215   0.0549788737   0.2586051702   0.2134474815   0.3107819522   0.7573332636   0.1339760226
    0.10   3.757380187000000   -0.66592977070000   -0.2318502043000000   -0.3411866240000000   -1.342289257800000   0.294832659500000   -0.0052217844000000000   7.65818369340000   0.9621640992   -0.1599922852   0.375213723700000   0.458697009700000   0.767187184100000   0.3926235601   0.710873789857342   -0.0033038247   0.0034685939   -0.00016344130000000000   0.0008352332   0.0007944174   0.0003493079   0.0028533136   -0.3438530779   -0.3902824195   0.7344036178   0.0613743936   0.0696615750   -0.1310838255   0.0465827158   0.0392612561   0.0542367588   0.2609819712   0.2199631313   0.3038641262   0.5828255648   0.1040286332
    0.15   3.876807696300000   -0.40425693250000   -0.2261910581000000   -0.2136343142000000   -1.212346856100000   0.243493138400000   -0.0069330665000000000   7.46776957670000   1.0657502041   -0.1767076596   0.362042816800000   0.462663925500000   0.766551393000000   0.3986259534   0.709954618183167   -0.0037064561   0.0033757771    0.00033171860000000000   0.0008392461   0.0007963701   0.0003501197   0.0029834549   -0.0720626778   -0.3408500604   0.4129748107   0.0131744619   0.0623140426   -0.0754998526   0.0386790408   0.0337127252   0.0426361232   0.2115695611   0.1844044328   0.2332143117   0.3764511925   0.0688226214
    0.20   3.577881511200000   -0.21664790570000   -0.2311220336000000   -0.1218093828000000   -1.047628389900000   0.206603903500000   -0.0079215285000000000   6.02971016370000   1.2073326171   -0.2002961687   0.364286000900000   0.471936638500000   0.758349340400000   0.3591951303   0.696024153921133   -0.0040165930   0.0034804929    0.00053670130000000000   0.0008387612   0.0007980689   0.0003516328   0.0031620497   -0.0939285934   -0.4029169502   0.4969280815   0.0168231126   0.0721645770   -0.0890024725   0.0401650673   0.0343146106   0.0459219043   0.2242538804   0.1915889877   0.2563960659   0.4366201866   0.0782010065
    0.22   3.554159735200000   -0.13572756200000   -0.2227849851000000   -0.1593324182000000   -1.024568232100000   0.198069574500000   -0.0079264169000000000   5.74696722800000   1.2316009842   -0.2043595571   0.361439062600000   0.478081315400000   0.756786799300000   0.3494363741   0.693762005050663   -0.0039890262   0.0032325563    0.00075722680000000000   0.0008377962   0.0007977073   0.0003529894   0.0030770306   -0.0456347874   -0.4319962538   0.4775105277   0.0081640110   0.0772836335   -0.0854260848   0.0394605921   0.0336556915   0.0452366702   0.2205748773   0.1881269290   0.2528617143   0.4341252333   0.0776645055
    0.24   3.519064278100000   -0.03875387410000   -0.2167649237000000   -0.1425607585000000   -0.994800641900000   0.182569615500000   -0.0078087913000000000   5.29971658150000   1.3376724978   -0.2221397257   0.356764818600000   0.487045377200000   0.762979475800000   0.3501790221   0.697939598218566   -0.0040530554   0.0032176004    0.00083850820000000000   0.0008461091   0.0008049311   0.0003569722   0.0031073939   -0.0542403686   -0.5268685888   0.5811083064   0.0096338060   0.0935788241   -0.1032125144   0.0422650715   0.0356048354   0.0493652374   0.2379613015   0.2004627623   0.2779367386   0.5139479410   0.0912839460
    0.26   3.436487773900000    0.00114579390000   -0.2249264473000000   -0.0544726476000000   -0.962135179400000   0.172871054200000   -0.0078078030000000000   4.97093936500000   1.3801871329   -0.2293432182   0.352807356200000   0.490437123900000   0.763485796300000   0.3470662166   0.696747129016816   -0.0039675618   0.0030756579    0.00087943080000000000   0.0008455532   0.0008042332   0.0003577044   0.0030226402   -0.0789499330   -0.5647868695   0.6435153239   0.0139121404   0.0995237608   -0.1133968734   0.0440472752   0.0368290486   0.0520517438   0.2499636515   0.2090009755   0.2953881685   0.5579736493   0.0983231711
    0.28   3.456222770200000    0.02231717340000   -0.2333002469000000   -0.0424403462000000   -0.970863683900000   0.169389862600000   -0.0073579578000000000   5.14990701910000   1.3937843451   -0.2317740783   0.354103535600000   0.494847931000000   0.764421014300000   0.3383217678   0.696222239882294   -0.0038723231   0.0030429743    0.00082938150000000000   0.0008466378   0.0008058952   0.0003593187   0.0029686300   -0.0911159427   -0.6086917288   0.7001198087   0.0159022845   0.1062337938   -0.1221905550   0.0454849837   0.0377130721   0.0542469412   0.2606170364   0.2160860250   0.3108207496   0.5999975931   0.1047164185
    0.30   3.481818236900000    0.10654454620000   -0.2263029865000000   -0.0418281324000000   -0.965917002300000   0.158837774800000   -0.0070098395000000000   5.12275065080000   1.4622066803   -0.2432367391   0.357390830500000   0.503136438200000   0.770257956200000   0.3307087198   0.700173363190729   -0.0039142966   0.0030844598    0.00082776590000000000   0.0008546790   0.0008141274   0.0003634575   0.0030019765   -0.1090753990   -0.6602785449   0.7691648086   0.0189743823   0.1148597910   -0.1338012719   0.0458502489   0.0377700352   0.0550473475   0.2635729648   0.2171233612   0.3164430495   0.6473255559   0.1126065334
    0.40   3.339757657000000    0.24296283960000   -0.2334327888000000    0.0102283108000000   -0.947306205300000   0.142390669200000   -0.0053852194000000000   4.75045583620000   1.7790031706   -0.2958875974   0.365850750100000   0.539648610200000   0.802382185800000   0.3180151259   0.725397142357700   -0.0036590364   0.0029637587    0.00069609560000000000   0.0008867237   0.0008460309   0.0003818721   0.0028462458   -0.2060016249   -0.7772232532   0.9831940942   0.0358496692   0.1352571688   -0.1711014808   0.0454041705   0.0370287168   0.0553070333   0.2609043014   0.2127767424   0.3178087550   0.7806178770   0.1358479220
    0.50   3.219837802700000    0.39216036780000   -0.1914544569000000   -0.2359285381000000   -0.946322046300000   0.163132167400000   -0.0049716692000000000   4.57971323480000   2.2361131713   -0.3725141419   0.381894169900000   0.527901989700000   0.824754120400000   0.3423108752   0.736002991171244   -0.0034264172   0.0023351975    0.00109047200000000000   0.0008919438   0.0008501866   0.0003841530   0.0025850208   -0.2935031361   -1.1131510245   1.4059797286   0.0504603184   0.1913777001   -0.2417220673   0.0528703908   0.0425162790   0.0645209093   0.3075213550   0.2472965214   0.3752867560   1.0959372117   0.1884182275
    0.75   2.997758622400000    0.66707938240000   -0.1692240497000000   -0.1778438233000000   -0.971905099600000   0.144334560000000   -0.0019729159000000000   4.68546622730000   2.9310863050   -0.4881588484   0.381587399500000   0.540956069100000   0.875412014200000   0.3864606506   0.766546963085415   -0.0022862902   0.0017519797    0.00051726090000000000   0.0008795037   0.0008419852   0.0003947747   0.0018436549   -0.3291736229   -1.5012660807   1.8306239869   0.0565863119   0.2580738699   -0.3146918609   0.0603104284   0.0483603549   0.0739467101   0.3508375353   0.2813216252   0.4301624481   1.4261185165   0.2451556918
    1.00   2.880339129900000    0.83747004290000   -0.1760783794000000   -0.1140374266000000   -0.989736511300000   0.128254469600000   -0.0009371899000000000   5.39161396920000   3.3475667959   -0.5576263173   0.369212497000000   0.522741073400000   0.890838358600000   0.4238718296   0.767621928874371   -0.0022565242   0.0018614242    0.00039449330000000000   0.0008841281   0.0008584518   0.0003905709   0.0018605520   -0.6034333548   -1.5807558710   2.1837482879   0.1034337848   0.2709554604   -0.3743136646   0.0671916459   0.0550942859   0.0820732834   0.3919964879   0.3214204134   0.4788160549   1.6455985014   0.2820700577
    1.50   2.311866313225240    1.12737122148565   -0.1272466291291850   -0.0940345619541096   -0.948072199937748   0.139283453079961    0.0000000000000000000   4.55349651778848   3.3947735776   -0.5657772605   0.364604388787861   0.534479589233590   0.908806163164938   0.4461378758   0.785903172060027    0.0000000000   0.0000000000    0.00000000000000000000   0.0000000000   0.0000000000   0.0000000000   0.0000000000   -0.7196136960   -1.3091708781   2.0281602604   0.1226701212   0.2231699468   -0.3457336433   0.0730655711   0.0654034180   0.0861148101   0.4286209646   0.3836728530   0.5051710731   1.5204384299   0.2591840142
    2.00   1.683732160380830    1.07923789414851   -0.1585659860388930   -0.2222592171080100   -0.911350017918323   0.161551084815657    0.0000000000000000000   4.30885604793099   3.3368325700   -0.5559975026   0.360101073292530   0.553135237617236   0.928121466837282   0.4626038673   0.805998580719113    0.0000000000   0.0000000000    0.00000000000000000000   0.0000000000   0.0000000000   0.0000000000   0.0000000000   -0.9520555035   -1.0089947716   1.9617675069   0.1621764158   0.1718756470   -0.3341742386   0.0764161941   0.0713315014   0.0885767609   0.4486007278   0.4187510752   0.5199892491   1.4632685429   0.2492582069
    3.00   1.057210789386420    1.47429408384738   -0.0388245283242518    0.0523996894533524   -0.855363161926190   0.160267276499267    0.0000000000000000000   4.36484245411132   2.9635284908   -0.4929821183   0.432637575150368   0.519351721688414   0.898236393544161   0.4147276555   0.793032477575311    0.0000000000   0.0000000000    0.00000000000000000000   0.0000000000   0.0000000000   0.0000000000   0.0000000000   -0.3942891131   -0.8311703475   1.2255274878   0.0687001767   0.1448215226   -0.2135335522   0.0617506639   0.0679966526   0.0725989097   0.3544039575   0.3902513962   0.4166650091   0.9662071056   0.1683500676
    4.00   0.754623572916101    1.77516800185502    0.0354551542781731    0.3019618968747080   -0.851637113897711   0.142613630697184    0.0000000000000000000   4.98982430836339   2.7071399686   -0.4506558103   0.429309829925598   0.507127364074350   0.871578899526473   0.3965493583   0.773780645294185    0.0000000000   0.0000000000    0.00000000000000000000   0.0000000000   0.0000000000   0.0000000000   0.0000000000   -0.3410199107   -0.7911405077   1.0206892052   0.0596115284   0.1382960265   -0.1784218738   0.0579631847   0.0674698178   0.0677166702   0.3315959389   0.3859794328   0.3873916767   0.8531916829   0.1491418665

    """)

    CONSTS = {"Mh": 6.75,
              "Mref": 5.5,
              "Rref": 1.0}


class KothaEtAl2016Italy(KothaEtAl2016):
    """
    Regional varient of the Kotha et al. (2016) GMPE for the Italy case
    """
    def _get_anelastic_coeff(self, C):
        """
        Returns the anelastic adjustment for the Italy case
        """
        return C["c3"] + C["Dc3IT"]

    def _get_regional_site_term(self, C):
        """
        Region specific site term for the Italy case
        """
        return C["Dg1IT"], C["Dg2IT"]


class KothaEtAl2016Turkey(KothaEtAl2016):
    """
    Regional varient of the Kotha et al. (2016) GMPE for the Turkey case
    """
    def _get_anelastic_coeff(self, C):
        """
        Returns the anelastic adjustment for the Turkey case
        """
        return C["c3"] + C["Dc3TR"]

    def _get_regional_site_term(self, C):
        """
        Region specific site term for the Turkey case
        """
        return C["Dg1TR"], C["Dg2TR"]


class KothaEtAl2016Other(KothaEtAl2016):
    """
    Regional varient of the Kotha et al. (2016) GMPE for the "Other" case
    """
    def _get_anelastic_coeff(self, C):
        """
        Returns the anelastic adjustment for the Other case
        """
        return C["c3"] + C["Dc3OTH"]

    def _get_regional_site_term(self, C):
        """
        Region specific site term for the Other case
        """
        return C["Dg1OTH"], C["Dg2OTH"]
