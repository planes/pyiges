import os

import numpy as np

from pyiges.check_imports import assert_full_module_variant, pyvista as pv
from pyiges.entity import Entity


def parse_float(str_value):
    """
    This function converts a string to float just like the built-in
    float() function. In addition to "normal" numbers it also handles
    numbers such as 1.2D3 (equivalent to 1.2E3).
    """
    try:
        return float(str_value)
    except ValueError:
        return float(str_value.lower().replace("d", "e"))


class Point(Entity):
    """IGES Point"""

    def _add_parameters(self, parameters):
        self.parameter_pointers = [False]*len(parameters)
        self._x = parse_float(parameters[1])
        self._y = parse_float(parameters[2])
        self._z = parse_float(parameters[3])

    @property
    def x(self):
        """X coordinate"""
        return self._x

    @property
    def y(self):
        """Y coordinate"""
        return self._y

    @property
    def z(self):
        """Z coordinate"""
        return self._z

    @property
    def coordinate(self):
        """Coordinate of the point as a numpy array"""
        return np.array([self._x, self._y, self._z])

    def __repr__(self):
        s = "--- IGES Point ---" + os.linesep
        s += f"{self._x}, {self._y}, {self._z} {os.linesep}"
        return s

    def __str__(self):
        return self.__repr__()

    @assert_full_module_variant
    def to_vtk(self):
        """Point represented as a ``pyvista.PolyData`` Mesh

        Returns
        -------
        mesh : ``pyvista.PolyData``
            ``pyvista`` mesh
        """
        return pv.PolyData([self.x, self.y, self.z])


class Line(Entity):
    """IGES Straight line segment"""

    def _add_parameters(self, parameters):
        self.parameters = parameters
        self.parameter_pointers = [False]*len(parameters)
        self._x1 = parse_float(parameters[1])
        self._y1 = parse_float(parameters[2])
        self._z1 = parse_float(parameters[3])
        self._x2 = parse_float(parameters[4])
        self._y2 = parse_float(parameters[5])
        self._z2 = parse_float(parameters[6])

    @property
    def coordinates(self):
        """Starting and ending point of the line as a ``numpy`` array"""
        return np.array(
            [[self._x1, self._y1, self._z1], [self._x2, self._y2, self._z2]]
        )

    def __repr__(self):
        s = "--- IGES Line ---" + os.linesep
        s += Entity.__str__(self) + os.linesep
        s += f"From point {self._x1}, {self._y1}, {self._z1} {os.linesep}"
        s += f"To point {self._x2}, {self._y2}, {self._z2}"
        return s

    @assert_full_module_variant
    def to_vtk(self, resolution=1):
        """Line represented as a ``pyvista.PolyData`` Mesh

        Returns
        -------
        mesh : ``pyvista.PolyData``
            ``pyvista`` mesh
        """
        return pv.Line(
            [self._x1, self._y1, self._z1], [self._x2, self._y2, self._z2], resolution
        )


class Transformation(Entity):
    """Transforms entities by matrix multiplication and vector
    addition to give a translation, as shown below:

    Notes
    -----
        | R11  R12  R13 |          | T1 |
    R=  | R21  R22  R23 |     T =  | T2 |
        | R31  R32  R33 |          | T3 |

    ET = RE + T, where E is the entity coordinate

    """

    def _add_parameters(self, parameters):
        """
        Index in list	Type of data	Name	Description
        1	REAL	R11	First row
        2	REAL	R12	..
        3	REAL	R13	..
        4	REAL	T1	First T vector value
        5	REAL	R21	Second row..
        ...
        12	REAL	T3	Third T vector value

        """
        self.parameters = parameters
        self.parameter_pointers = [False]*len(parameters)
        self.r11 = parse_float(parameters[1])
        self.r12 = parse_float(parameters[2])
        self.r13 = parse_float(parameters[3])
        self.t1 = parse_float(parameters[4])
        self.r21 = parse_float(parameters[5])
        self.r22 = parse_float(parameters[6])
        self.r23 = parse_float(parameters[7])
        self.t2 = parse_float(parameters[8])
        self.r31 = parse_float(parameters[9])
        self.r32 = parse_float(parameters[10])
        self.r33 = parse_float(parameters[11])
        self.t3 = parse_float(parameters[12])

    def __repr__(self):
        txt = "IGES 124 Transformation Matrix\n"
        txt += str(self.to_affine())
        return txt

    def to_affine(self):
        """Return a 4x4 affline transformation matrix"""
        return np.array(
            [
                [self.r11, self.r12, self.r13, self.t1],
                [self.r21, self.r22, self.r23, self.t2],
                [self.r31, self.r32, self.r33, self.t3],
                [0, 0, 0, 1],
            ]
        )

    @assert_full_module_variant
    def _to_vtk(self):
        """Convert to a vtk transformation matrix"""
        vtkmatrix = pv.vtkmatrix_from_array(self.to_affine())
        import vtk

        trans = vtk.vtkTransform()
        trans.SetMatrix(vtkmatrix)
        return trans


class ConicArc(Entity):
    """Conic Arc (Type 104)
    Arc defined by the equation:
    ``A*x**2 + B*x*y + C*y**2 + D*x + E*y + F = 0``

    with a Transformation Matrix (Entity 124). Can define
    an ellipse, parabola, or hyperbola.

    """

    # The definitions of the terms ellipse, parabola, and hyperbola
    # are given in terms of the quantities Q1, Q2, and Q3. These
    # quantities are:

    #     |  A   B/2  D/2 |        |  A   B/2 |
    # Q1= | B/2   C   E/2 |   Q2 = | B/2   C  |   Q3 = A + C
    #     | D/2  E/2   F  |
    # A parent conic curve is:

    # An ellipse if Q2 > 0 and Q1, Q3 < 0.
    # A hyperbola if Q2 < 0 and Q1 != 0.
    # A parabola if Q2 = 0 and Q1 != 0.

    def _add_parameters(self, parameters):
        """
        Index	Type	Name	Description
        1	REAL	A	coefficient of xt^2
        2	REAL	B	coefficient of xtyt
        3	REAL	C	coefficient of yt^2
        4	REAL	D	coefficient of xt
        5	REAL	E	coefficient of yt
        6	REAL	F	scalar coefficient
        7	REAL	X1	x coordinate of start point
        8	REAL	Y1	y coordinate of start point
        9	REAL	Z1	z coordinate of start point
        10	REAL	X2	x coordinate of end point
        11	REAL	Y2	y coordinate of end point
        12	REAL	Z2	z coordinate of end point
        """
        self.parameters = parameters
        self.parameter_pointers = [False]*len(parameters)
        self.a = parameters[1]  #  coefficient of xt^2
        self.b = parameters[2]  #  coefficient of xtyt
        self.c = parameters[3]  #  coefficient of yt^2
        self.d = parameters[4]  #  coefficient of xt
        self.e = parameters[5]  #  coefficient of yt
        self.f = parameters[6]  #  scalar coefficient
        self.x1 = parameters[7]  #  x coordinate of start point
        self.y1 = parameters[8]  #  y coordinate of start point
        self.z1 = parameters[9]  #  z coordinate of start point
        self.x2 = parameters[10]  #  x coordinate of end point
        self.y2 = parameters[11]  #  y coordinate of end point
        self.z2 = parameters[12]  #  z coordinate of end point

    def __repr__(self):
        info = "Conic Arc\nIGES Type 104\n"
        info += f"Start:  ({self.x1:f}, {self.y1:f}, {self.z1:f})\n"
        info += f"End:    ({self.x2:f}, {self.y2:f}, {self.z2:f})\n"
        info += "Coefficient of x**2: %f" % self.a
        info += "Coefficient of x*y:  %f" % self.b
        info += "Coefficient of y**2: %f" % self.c
        info += "Coefficient of x:    %f" % self.d
        info += "Coefficient of y:    %f" % self.e
        info += "Scalar coefficient:  %f" % self.f
        return info

    @assert_full_module_variant
    def to_vtk(self):
        # a*x**2 + b*x*y + c*y**2 + d*x + e*y + f = 0
        # from sympy import Symbol
        # from sympy.solvers import Solve
        # a = Symbol('a')
        # b = Symbol('b')
        # c = Symbol('c')
        # d = Symbol('d')
        # e = Symbol('e')
        # f = Symbol('f')
        # x = Symbol('x')
        # y = Symbol('y')
        # solve(a*x**2 + b*x*y + c*y**2 + d*x + e*y + f, x)

        # x0 = (-b*y - d + sqrt(-4*a*c*y**2 - 4*a*e*y - 4*a*f + b**2*y**2 + 2*b*d*y + d**2))/(2*a)
        # x1 = -(b*y + d + sqrt(-4*a*c*y**2 - 4*a*e*y - 4*a*f + b**2*y**2 + 2*b*d*y + d**2))/(2*a)

        raise NotImplementedError("Not yet implemented")
    

class Parametric_Spline_Curve(Entity):
    """"""

    def _add_parameters(self, parameters):
        self.parameters= parameters
        self.parameter_pointers = [False]*len(parameters)
    
    
class Surface_of_Revolution(Entity):
    """
            Parameter Data
    Index	Type	Name	Description
        1	Pointer	Axis	Pointer to Line describing axis of rotation
        2	Pointer	Surface	Pointer to generatrix entity
        3	REAL	SA	Start angle (Rad)
        4	REAL	EA	End angle (Rad)

    """      

    def _add_parameters(self, parameters):
        self.parameters = parameters
        self.parameter_pointers = [False,True,True,False,False]
        self.axis    = int(parameters[1])
        self.surface = int(parameters[2])
        self.SA      = float(parameters[3])
        self.EA      = float(parameters[4])
    
class Tabulated_Cylinder(Entity):
    
    def _add_parameters(self, parameters):
        """
                Parameter Data
        Index	Type	Name	Description
        1	Pointer	Curve	Pointer to directrix
        2	REAL	Lx	x coordinate of line end
        3	REAL	Ly	y coordinate of line end
        4	REAL	Lz	z coordinate of line end

        """        
        self.parameters = parameters
        self.parameter_pointers = [False,True,False,False,False]    
        self.curve = int(parameters[1])
        self.Lx    = float(parameters[2])
        self.Ly    = float(parameters[3])
        self.Lz    = float(parameters[4])
    


class RationalBSplineCurve(Entity):
    """Rational B-Spline Curve
    IGES Spec v5.3 p. 123 Section 4.23
    See also Appendix B, p. 545
    """

    def _add_parameters(self, parameters):
        self.parameters = parameters
        self.parameter_pointers = [False]*len(parameters)
        self.K = int(parameters[1])
        self.M = int(parameters[2])
        self.prop1 = int(parameters[3])
        self.prop2 = int(parameters[4])
        self.prop3 = int(parameters[5])
        self.prop4 = int(parameters[6])

        self.N = 1 + self.K - self.M
        self.A = self.N + 2 * self.M

        # Knot sequence
        self.T = []
        for i in range(7, 7 + self.A + 1):
            self.T.append(parse_float(parameters[i]))

        # Weights
        self.W = []
        for i in range(self.A + 8, self.A + self.K + 8):
            self.W.append(parse_float(parameters[i]))

        # Control points
        self.control_points = []
        for i in range(9 + self.A + self.K, 9 + self.A + 4 * self.K + 1, 3):
            point = (
                parse_float(parameters[i]),
                parse_float(parameters[i + 1]),
                parse_float(parameters[i + 2]),
            )
            self.control_points.append(point)

        # Parameter values
        self.V0 = parse_float(parameters[12 + self.A + 4 * self.K])
        self.V1 = parse_float(parameters[13 + self.A + 4 * self.K])

        # Unit normal (only for planar curves)
        if len(parameters) > 14 + self.A + 4 * self.K + 1:
            self.planar_curve = True
            self.XNORM = parse_float(parameters[14 + self.A + 4 * self.K])
            self.YNORM = parse_float(parameters[15 + self.A + 4 * self.K])
            self.ZNORM = parse_float(parameters[16 + self.A + 4 * self.K])
        else:
            self.planar_curve = False

    def __str__(self):
        s = "--- Rational B-Spline Curve ---" + os.linesep
        s += Entity.__str__(self) + os.linesep
        s += str(self.T) + os.linesep
        s += str(self.W) + os.linesep
        s += str(self.control_points) + os.linesep
        s += f"Parameter: v(0) = {self.V0}    v(1) = {self.V1}" + os.linesep
        if self.planar_curve:
            s += f"Unit normal: {self.XNORM} {self.YNORM} {self.ZNORM}"
        return s

    @assert_full_module_variant
    def to_geomdl(self):
        from geomdl import NURBS

        curve = NURBS.Curve()
        curve._kv_normalize = False
        curve.degree = self.M
        curve.ctrlpts = self.control_points
        curve.weights = self.W + [1]
        curve.knotvector = self.T  # Set knot vector
        return curve

    @assert_full_module_variant
    def to_vtk(self, delta=0.01):
        """Set evaluation delta (controls the number of curve points)"""
        # Create a 3-dimensional B-spline Curve
        curve = self.to_geomdl()
        curve.delta = delta

        # spline segfaults here sometimes...
        # return pv.Spline(np.array(curve.evalpts))

        n_points = len(curve.evalpts)
        faces = np.arange(-1, n_points)
        faces[0] = n_points
        line = pv.PolyData()
        line.points = np.array(curve.evalpts)
        line.lines = faces
        return line


class RationalBSplineSurface(Entity):
    """Rational B-Spline Surface


    Examples
    --------
    >>> import pyiges
    >>> from pyiges import examples
    >>> iges = pyiges.read(examples.impeller)
    >>> bsurfs = igs.bspline_surfaces()
    >>> bsurf = bsurfs[0]
    >>> print(bsurf)
        Rational B-Spline Surface
        Upper index of first sum:        3
        Upper index of second sum:       3
        Degree of first basis functions: 3
        Degree of second basis functions: 3
        Open in the first direction
        Open in the second direction
        Polynomial
        Periodic in the first direction
        Periodic in the second direction
        Knot 1: [0. 0. 0. 0. 1. 1. 1. 1.]
        Knot 2: [0. 0. 0. 0. 1. 1. 1. 1.]
        u0: 1.000000
        u1: 0.000000
        v0: 1.000000
        v1: 128.000000
        Control Points: 16

    >>> bsurf.control_points
    array([[-26.90290533, -16.51153913,  -8.87632351],
           [-25.85182035, -15.86644037, -21.16779478],
           [-25.99572556, -15.95476156, -33.51982653],
           [-27.33276363, -16.77536276, -45.77299513],
           [-28.23297477, -14.34440426,  -8.87632351],
           [-27.12992455, -13.78397453, -21.16779478],
           [-27.28094438, -13.86070358, -33.51982653],
           [-28.6840851 , -14.57360111, -45.77299513],
           [-29.29280315, -12.03305788,  -8.87632351],
           [-28.14834588, -11.56293146, -21.16779478],
           [-28.3050348 , -11.62729699, -33.51982653],
           [-29.76084756, -12.22532372, -45.77299513],
           [-30.06701039,  -9.61104189,  -8.87632351],
           [-28.89230518,  -9.2355426 , -21.16779478],
           [-29.05313537,  -9.28695263, -33.51982653],
           [-30.54742519,  -9.76460843, -45.77299513]])
    """

    @property
    def k1(self):
        """Upper index of first sum"""
        return self._k1

    @property
    def k2(self):
        """Upper index of second sum"""
        return self._k2

    @property
    def m1(self):
        """Degree of first basis functions"""
        return self._m1

    @property
    def m2(self):
        """Degree of second basis functions"""
        return self._m2

    @property
    def flag1(self):
        """Closed in the first direction"""
        return self._flag1

    @property
    def flag2(self):
        """Closed in the second direction"""
        return self._flag2

    @property
    def flag3(self):
        """Polynominal

        ``False`` - rational
        ``True``  - polynomial
        """
        return self._flag3

    @property
    def flag4(self):
        """First direction periodic"""
        return self._flag4

    @property
    def flag5(self):
        """Second direction Periodic"""
        return self._flag5

    @property
    def knot1(self):
        """First Knot Sequences"""
        return self._knot1

    @property
    def knot2(self):
        """Second Knot Sequences"""
        return self._knot2

    @property
    def weights(self):
        """First Knot Sequences"""
        return self._weights

    def control_points(self):
        """Control points"""
        return self._cp

    @property
    def u0(self):
        """Start first parameter value"""
        return self._u0

    @property
    def u1(self):
        """End first parameter value"""
        return self._u1

    @property
    def v0(self):
        """Start second parameter value"""
        return self._v0

    @property
    def v1(self):
        """End second parameter value"""
        return self._v1

    def _add_parameters(self, input_parameters):
        parameters = np.array(
            [parse_float(param) for param in input_parameters], dtype=float
        )

        self.parameters = input_parameters
        self.parameter_pointers = [False]*len(parameters)
        self._k1 = int(parameters[1])  # Upper index of first sum
        self._k2 = int(parameters[2])  # Upper index of second sum
        self._m1 = int(parameters[3])  # Degree of first basis functions
        self._m2 = int(parameters[4])  # Degree of second basis functions
        self._flag1 = bool(parameters[5])  # 0=closed in first direction, 1=not closed
        self._flag2 = bool(parameters[6])  # 0=closed in second direction, 1=not closed
        self._flag3 = bool(parameters[7])  # 0=rational, 1=polynomial
        self._flag4 = bool(
            parameters[8]
        )  # 0=nonperiodic in first direction , 1=periodic
        self._flag5 = bool(
            parameters[9]
        )  # 0=nonperiodic in second direction , 1=periodic

        # load knot sequences
        self._knot1 = parameters[10 : 12 + self._k1 + self._m1]
        self._knot2 = parameters[
            12 + self._k1 + self._m1 : 14 + self._k2 + self._m1 + self._k1 + self._m2
        ]

        # weights
        st = 14 + self._k2 + self._m1 + self._k1 + self._m2
        en = st + (1 + self._k2) * (1 + self._k1)
        self._weights = parameters[st:en]

        # control points
        st = (
            14
            + self._k2
            + self._k1
            + self._m1
            + self._m2
            + (1 + self._k2) * (1 + self._k1)
        )
        en = st + 3 * (1 + self._k2) * (1 + self._k1)
        self._cp = parameters[st:en].reshape(-1, 3)

        self._u0 = parameters[en]    # Start first parameter value
        self._u1 = parameters[en+1]  # End first parameter value
        self._v0 = parameters[en+2]  # Start second parameter value
        self._v1 = parameters[en+3]  # End second parameter value

    def __repr__(self):
        info = "Rational B-Spline Surface\n"
        info += "    Upper index of first sum:          %d\n" % self._k1
        info += "    Upper index of second sum:         %d\n" % self._k2
        info += "    Degree of first basis functions:   %d\n" % self._m1
        info += "    Degree of second basis functions:  %d\n" % self._m2

        if self.flag1:
            info += "    Closed in the first direction\n"
        else:
            info += "    Open in the first direction\n"

        if self.flag2:
            info += "    Closed in the second direction\n"
        else:
            info += "    Open in the second direction\n"

        if self.flag3:
            info += "    Rational\n"
        else:
            info += "    Polynomial\n"

        if self.flag4:
            info += "    Nonperiodic in first direction\n"
        else:
            info += "    Periodic in the first direction\n"

        if self.flag5:
            info += "    Nonperiodic in second direction\n"
        else:
            info += "    Periodic in the second direction\n"

        info += "    Knot 1: %s\n" % str(self.knot1)
        info += "    Knot 2: %s\n" % str(self.knot2)

        info += "    u0: %f\n" % self.u0
        info += "    u1: %f\n" % self.u1
        info += "    v0: %f\n" % self.v0
        info += "    v1: %f\n" % self.v1

        info += "    Control Points: %d" % len(self._cp)
        return info

    @assert_full_module_variant
    def to_geomdl(self):
        """Return a ``geommdl.BSpline.Surface``"""
        from geomdl import BSpline

        surf = BSpline.Surface(normalize_kv=False)

        # Set degrees
        surf.degree_u = self._m2
        surf.degree_v = self._m1

        # set control points and knots
        cp2d = self._cp.reshape(self._k2 + 1, self._k1 + 1, 3)
        surf.ctrlpts2d = cp2d.tolist()
        surf.knotvector_u = self._knot2
        surf.knotvector_v = self._knot1

        # set weights
        surf.weights = self._weights
        return surf

    @assert_full_module_variant
    def to_vtk(self, delta=0.025):
        """Return a pyvista.PolyData Mesh

        Parameters
        ----------
        delta : float, optional
            Resolution of the surface.  Higher number result in a
            denser mesh at the cost of compute time.

        Returns
        -------
        mesh : ``pyvista.PolyData``
            ``pyvista`` mesh

        Examples
        --------
        >>> mesh = bsurf.to_vtk()
        >>> mesh.plot()
        """
        surf = self.to_geomdl()
        # Set evaluation delta
        surf.delta = delta

        # Evaluate surface points
        surf.evaluate()

        faces = []
        for face in surf.faces:
            faces.extend([3] + face.vertex_ids)

        return pv.PolyData(np.array(surf.vertices), np.array(faces))


class CircularArc(Entity):
    """Circular Arc

    Type 100: Simple circular arc of constant radius. Usually defined
    with a Transformation Matrix Entity (Type 124).

    """

    def _add_parameters(self, parameters):
        # Index in list    Type of data    Name    Description
        # 1                REAL            Z       z displacement on XT,YT plane
        # 2                REAL            X       x coordinate of center
        # 3                REAL            Y       y coordinate of center
        # 4                REAL            X1      x coordinate of start
        # 5                REAL            Y1      y coordinate of start
        # 6                REAL            X2      x coordinate of end
        # 7                REAL            Y2      y coordinate of end
        self.parameters = parameters
        self.parameter_pointers = [False]*len(parameters)
        self.z = parse_float(parameters[1])
        self.x = parse_float(parameters[2])
        self.y = parse_float(parameters[3])
        self.x1 = parse_float(parameters[4])
        self.y1 = parse_float(parameters[5])
        self.x2 = parse_float(parameters[6])
        self.y2 = parse_float(parameters[7])
        self._transform = self.d.get("transform", None)

    @assert_full_module_variant
    def to_vtk(self, resolution=20):
        """Circular arc represented as a ``pyvista.PolyData`` Mesh

        Returns
        -------
        mesh : ``pyvista.PolyData``
            ``pyvista`` mesh
        """
        start = [self.x1, self.y1, 0]
        end = [self.x2, self.y2, 0]
        center = [self.x, self.y, 0]
        arc = pv.CircularArc(
            center=center, pointa=start, pointb=end, resolution=resolution
        )
        arc.points += [0, 0, self.z]
        if self.transform is not None:
            arc.transform(self.transform._to_vtk())

        return arc

    @property
    def transform(self):
        if self._transform is not None:
            return self.iges[self._transform]

    def __repr__(self):
        info = "Circular Arc\nIGES Type 100\n"
        info += f"Center: ({self.x:f}, {self.y:f})\n"
        info += f"Start:  ({self.x1:f}, {self.y1:f})\n"
        info += f"End:    ({self.x2:f}, {self.y2:f})\n"
        info += "Z Disp: %f" % self.z
        return info


class Composite_Curve(Entity):
    """Groups other curves to form a composite. Can use Ordered List, Point, 
    Connected Point, and Parameterized Curve entities."""
    
    
    def _add_parameters(self, parameters):
        """
                Parameter Data
        Index	Type	Name	Description
        1	REAL	N	Number of curves comprising this entity
        2	Pointer	DE(1)	Pointer to first curve
        
        1+N	Pointer	DE(N)	Pointer to last curve
        """
        self.parameters     = parameters
        self.parameter_pointers = [False,False]
        self.N_curves       = int(parameters[1])
        self.curves         = []
        for ii in range(self.N_curves):
            self.curves.append(int(parameters[ii+2]))
            self.parameter_pointers.append(True)
            
    def get_curves(self):
        curves = []
        for curve_ptr in self.curves:
            curves.append(self.iges.from_pointer(curve_ptr))
        return curves
    
class Curve_On_A_Parametric_Surface(Entity):
    """Associates a curve and a surface, gives how a curve lies on the specified surface."""
    
    def _add_parameters(self, parameters):
        """
                Parameter Data
        Index	Type	Name	Description
        1	INT	Flag1	Indicates how curve was created:
                                0 = Unspecified
                                1 = Projection
                                2 = Intersection of surfaces
                                3 = Isoparametric curve
        2	Pointer	Surface	Points to surface curve lies on
        3	Pointer	Curve	Definition of curve
        4	Pointer	Mapping	Entity that provides mapping from curve to surface
        5	INT	Representation	Preferred representation of curve:
                                0 = Unspecified
                                1 = S(B(t))
                                2 = C(t)
                                3 = Both equal
        """
        self.parameters       = parameters
        self.parameter_pointers = [False,False,True,True,True,False]
        self.parameter_pointers.extend([False]*(len(parameters)-len(self.parameter_pointers)))
        self.how_created      = int(parameters[1])
        self.surface_pointer  = int(parameters[2])
        self.curve_pointer    = int(parameters[3])
        self.mapping          = int(parameters[4])
        self.representation   = parameters[5]
        
    def get_surface(self):
        return self.iges.from_pointer(self.surface_pointer)
    
    def get_curve(self):
        return self.iges.from_pointer(self.curve_pointer)    
    
class Trimmed_Surface(Entity):
    
        def _add_parameters(self, parameters):
            """
                    Parameter Data
            Index	Type	Name	Description
            1	        Pointer	Surface	Entity to be trimmed
            2	        INT	Flag	0=Boundary is boundary of surface, 1=otherwise
            3	        INT	N	Number of closed curves that make up inner boundary
            4	        Pointer	OuterBound Pointer to Curve on Parametric Surface
                                        (Type 142) entity that is outer bound
            5	Pointer	Inner1	Pointer to first inner curve boundary
            5+N	Pointer	InnerN	Pointer to last inner curve boundary
            """
            self.parameters         = parameters
            self.parameter_pointers = [False,True,False,False,True]
            self.surface_pointer    = int(parameters[1])
            self.flag_boundary      = int(parameters[2])
            self.n_inner_boundary   = int(parameters[3])
            self.OuterBound         = int(parameters[4])
            self.inner_curve_boundary = []
            for ii in range(self.n_inner_boundary):
                self.inner_curve_boundary.append(parameters[5+ii])
                self.parameter_pointers.append(True)
            self.parameter_pointers.extend([False]*(len(parameters)-len(self.parameter_pointers)))
                
                
        def get_surface(self):
            return self.iges.from_pointer(self.surface_pointer)
        
        def get_outerboundary(self):
            return self.iges.from_pointer(self.OuterBound)   
        
        
class Boundary:
    """Identifies a surface boundary consisting of curves lying on a surface."""

    def _add_parameters(self, parameters):
        """
        Parameter Data
        Index	Type	Name	Description
        1	INT	Type	The type of boundary being represented
                                0=Entities reference model space curves
                                1=Entities reference model space curves and
                                associated parameter space curves
        2	INT	Pref	Preferred representation of trimming curves.
                                0 = Unspecified
                                1 = Model Space
                                2 = Parameter Space
                                3 = Equal
        3	Pointer	Surface	The untrimmed surface to be bounded
        4	INT	N	Number of curves in boundary
        5	Pointer	MC1	Pointer to first model space curve
        6	INT	Flag 1	Orientation flag: 0 = No reversal
                                1 = Reversal needed
        7	INT	K1	How many parameter curves for this model curve
        8	Pointer	PC(1,1)	First parameter curve for model curve 1
        7+K1	Pointer	PC(1,K1)	Last parameter curve for model curve 1
        8+K1	Pointer	MC2	Model curve 2
        11+3N+Sum(K(N))	Pointer	PC(N,KN)	Last parameter curve for model curve N

        """

        self.parameters = parameters
        self.Type            = int(parameters[1])
        self.pref            = int(parameters[2])
        self.surface_pointer = int(parameters[3])
        self.N               = int(parameters[4])
        self.space_curves    = []
        self.model_curves    = []
        self.Flags           = []
        index =  5
        for _ in range(self.N):
            space_curve, flag_1, list_curves,index  = unpack_boundary_curves_parameters(parameters, index)
            self.space_curves.append(space_curve)
            self.Flags.append(flag_1)
            self.model_curves.append(list_curves)
            
            
    def get_space_curves(self):
        scs = []
        for sc in self.space_curves:
            scs.append(self.iges.from_pointer(sc))
        return sc
    def get_surface(self):
        return self.iges.from_pointer(self.surface_pointer)
    def get_model_curves(self):
        mcs = []
        for mc in self.model_curves:
            mcs.append(self.iges.from_pointer(mc))
        return mc
        
        

        
def unpack_boundary_curves_parameters(parameters,start_index):
    
    # Get the parameters
    space_curve = parameters[start_index]
    flag_1      = parameters[start_index+1]
    K1          = parameters[start_index+2]
    end_index   = start_index + 3 + K1 
    list_curves = parameters[(start_index+3):end_index]
    
    return space_curve, flag_1, list_curves, end_index +1
            

        
class Bounded_Surface:
    """Represents a surface bounded by Boundary Entities."""

    def _add_parameters(self, parameters):    
        """
        Parameter Data
        Index	Type	Name	Description     
        1	INT	Type	The type of boundary being represented
                                0=Entities reference model space curves
                                1=Entities reference model space curves and
                                associated parameter space curves
        2	Pointer	Surface	Points to unbounded surface
        3	INT	N	Number of Boundary entities
        4	Pointer	B1	Pointer to first boundary entity
        3+N	Pointer	BN	Pointer to last boundary entity   
        """
        self.parameters      = parameters
        self.parameter_pointers  = [False,False,True,False]
        self.Type            = int(parameters[1])
        self.surface_pointer = int(parameters[2])
        self.N_boundaries    = int(parameters[3])
        self.B               = []  # List of boundaries
        for ii in range(4,4+self.N_boundaries):
            self.B.append(int(parameters[ii]))
            self.parameter_pointers[True]
            
    def get_surface(self):
        return self.iges.from_pointer(self.surface_pointer)
    
    def get_boundaries(self):
        Bs = []
        for B in self.B:
            Bs.append(self.iges.from_pointer(B))
        return Bs
            
        
class Subfigure(Entity):
    
    def _add_parameters(self,parameters):    
        """
                Parameter Data
        Index	Type	Name	Description
        1	INT	Depth	Depth of subfigure (with nesting)
        2	String	Name	Subfigure Name
        3	INT	N	Number of entities in subfigure
        4	Pointer	E1	Associated entity 1
        .	.
        .	.
        3+N	Pointer	EN	Last associated entity
        """
        self.parameters          = parameters
        self.parameter_pointers  = [False,False,False,False]
        self.Depth_of_subfigure  = int(parameters[1])
        self.Subfigure_Name      = str(parameters[2])
        self.Number_of_entities  = int(parameters[3])
        self.pointers            = [int(x) for x in parameters[4:4+self.Number_of_entities]]
        self.parameter_pointers.extend([True]*self.Number_of_entities)
        self.parameter_pointers.extend([False]*(len(parameters)-len(self.parameter_pointers)))
        
            
    def get_pointers(self):
        return self.iges.from_pointer(self.pointers)

class Color(Entity):
    """
            Parameter Data
    Index	Type	Name	Description
        1	REAL	RED	Red value, from 0.0 - 100.0
        2	REAL	GREEN	Green value, from 0.0 - 100.0
        3	REAL	BLUE	Blue value, from 0.0 - 100.0
        4	String	Name	Optional color name
    """    

    def _add_parameters(self, parameters):
        self.parameters = parameters
        self.parameter_pointers = [False]*len(parameters)
        self.RED   = float(parameters[1])
        self.GREEN = float(parameters[2])
        self.BLUE  = float(parameters[3])
        
        
class Property_Entity(Entity):
    """
            Parameter Data
    Index	Type	Name	Description    
        1	Integer	NP	Number of property values
        2	VariableV(1)	First property value
        .	.
        1+NP	VariableV(NP)	Last property value
    """
    
    def _add_parameters(self,parameters):
        self.parameters
        self.parameter_pointers = [False]*len(parameters)
        
class Singular_Subgfigure_Instance(Entity):
    """
                Parameter Data
    Index	Type	Name	Description
        1	Pointer	DE	Pointer to the DE of the Subfigure Definition Entity
        2	REAL	X	Translation data relative to either model space or to the definition space of a referring entity
        3	REAL	Y
        4	REAL	Z
        5	REAL	S	Scale factor (default = 1.0)

    """
    def _add_parameters(self,parameters):
        self.parameters = parameters
        self.parameter_pointers = [False,True,False,False,False,False]
        self.pointer  = int(parameters[1])
        self.X = float(parameters[2])
        self.Y = float(parameters[3])      
        self.Z = float(parameters[4])            
        self.S = float(parameters[5])     
        self.parameter_pointers.extend([False]*(len(parameters)-len(self.parameter_pointers)))
 
        
    
    
        
#class Definition_Levels(Entity):
    #
            #Parameter Data
    #Index	Type	Name	Description
        #1	Integer	NP	Number of property values
        #2	Integer	L(1)	First level number
        #.	.
        #1+NP	Integer	L(NP)	Last level number
    #"""    

    #def _add_parameters(self, parameters):
        #self.parameters = parameters
        #self.NP         = int(parameters[1])
        #self.L          = parameters[2:]



        

class Face(Entity):
    """Defines a bound portion of three dimensional space (R^3) which
    has a finite area. Used to construct B-Rep Geometries."""

    def _add_parameters(self, parameters):
        """
        Parameter Data
        Index	Type	Name	Description
        Pointer	Surface	Underlying surface
        2	INT	N	Number of loops
        3	BOOL	Flag	Outer loop flag:
                                True indicates Loop1 is outer loop.
                                False indicates no outer loop.
        4	Pointer	Loop1	Pointer to first loop of the face
        3+N	Pointer	LoopN	Pointer to last loop of the face
        """
        self.surf_pointer = int(parameters[1])
        self.n_loops = int(parameters[2])
        self.outer_loop_flag = bool(parameters[3])

        self.loop_pointers = []
        for i in range(self.n_loops):
            self.loop_pointers.append(int(parameters[4 + i]))

    @property
    def loops(self):
        loops = []
        for ptr in self.loop_pointers:
            loops.append(self.iges.from_pointer(ptr))

        return loops

    def __repr__(self):
        info = "IGES Type 510: Face\n"
        # info += 'Center: (%f, %f)\n' % (self.x, self.y)
        # info += 'Start:  (%f, %f)\n' % (self.x1, self.y1)
        # info += 'End:    (%f, %f)\n' % (self.x2, self.y2)
        # info += 'Z Disp: %f' % self.z
        return info


class Loop(Entity):
    """Defines a loop, specifying a bounded face, for B-Rep
    geometries."""

    def _add_parameters(self, parameters):
        """Parameter Data
        Index   Type    Name                Description
        1       INT     N                   N Edges in loop
        2	INT	Type1	            Type of Edge 1
                                            0 = Edge
                                            1 = Vertex
        3	Pointer	E1                  First vertex list or edge list
        4	INT	Index1              Index of edge/vertex in E1
        5	BOOL	Flag1               Orientation flag -
                                            True = Agrees with model curve
        6	INT	K1                  Number of parametric space curves
        7	BOOL	ISO(1, 1)           Isoparametric flag of first
                                            parameter space curve
        8	Pointer	PSC(1, 1)           First parametric space curve of E1
        .
        6+2K1	Pointer	PSC(1, K1)          Last parametric space curve of E1
        7+2K1	INT	Type2               Type of Edge 2
        """
        self.parameters = parameters
        self.n_edges = int(self.parameters[1])
        self._edges = []

        c = 0
        for i in range(self.n_edges):
            edge = {
                "type": int(self.parameters[2 + c]),
                "e1": int(self.parameters[3 + c]),  # first vertex or edge list
                "index1": int(self.parameters[4 + c]),  # index of edge in e1
                "flag1": bool(self.parameters[5 + c]),  # orientation flag
                "k1": int(self.parameters[6 + c]),
            }  # n curves
            curves = []
            for j in range(edge["k1"]):
                curve = {
                    "iso": bool(self.parameters[7 + c + j * 2]),  # isopara flag
                    "psc": int(self.parameters[8 + c + j * 2]),
                }  # space curve
                curves.append(curve)
            c += 5 + 2 * edge["k1"]

            edge["curves"] = curves
            self._edges.append(edge)

    # @property
    # def edge_lists(self):
    #     for

    def curves(self):
        """list of curves"""
        pass

    def __repr__(self):
        info = "IGES Type 508: Loop\n"
        return info


class EdgeList(Entity):
    """Provides a list of edges, comprised of vertices, for specifying
    B-Rep Geometries."""

    _iges_type = 504

    def _add_parameters(self, parameters):
        """
        Parameter Data
        Index in list	Type of data	Name	Description
        INT	N	Number of Edges in list
        2	Pointer	Curve1	First model space curve
        3	Pointer	SVL1	Vertex list for start vertex
        4	INT	S1	Index of start vertex in SVL1
        5	Pointer	EVL1	Vertex list for end vertex
        6	INT	E1	Index of end vertex in EVL1
        .
        .	.
        .	.
        .
        5N-3	Pointer	CurveN	First model space curve
        5N-2	Pointer	SVLN	Vertex list for start vertex
        5N-1	INT	SN	Index of start vertex in SVLN
        5N	Pointer	EVLN	Vertex list for end vertex
        5N+1	INT	EN	Index of end vertex in EVLN
        """
        self.parameters = parameters
        self.n_edges = int(parameters[1])

        self.edges = []
        for i in range(self.n_edges):
            edge = {
                "curve1": int(parameters[2 + 5 * i]),  # first model space curve
                "svl": int(parameters[3 + 5 * i]),  # vertex list for start vertex
                "s": int(parameters[4 + 5 * i]),  # start index
                "evl": int(parameters[5 + 5 * i]),  # vertex list for end vertex
                "e": int(parameters[6 + 5 * i]),
            }  # index of end vertex in evl n
            self.edges.append(edge)

    # @property
    # def curve(self, ):
    #     for

    def __getitem__(self, indices):
        # TODO: limit spline based on start and end point
        ptr = self.edges[indices]["curve1"]
        return self.iges.from_pointer(ptr)

    def __len__(self):
        return len(self.edges)

    def __repr__(self):
        """Return the representation of EdgesList."""
        return "IGES Type {self._iges_type}: Edge List\n"


class VertexList(Entity):
    """Vertex List (Type 502 Form 1)"""

    _iges_type = 502

    def _add_parameters(self, parameters):
        """Adds Parameter Data.

        Index in list	Type of data	Name	Description
        INT	N	Number of vertices in list
        2	REAL	X1	Coordinates of first vertex
        3	REAL	Y1
        4	REAL	Z1
        .
        .	.
        .	.
        .
        3N-1	REAL	XN	Coordinates of last vertex
        3N	REAL	YN
        3N+1	REAL	ZN
        """
        self.parameters = parameters
        self.parameter_pointers = [False]*len(parameters)
        self.n_points = int(parameters[1])
        self.points = []
        for i in range(self.n_points):
            point = [
                parse_float(self.parameters[2 + i * 3]),
                parse_float(self.parameters[3 + i * 3]),
                parse_float(self.parameters[4 + i * 3]),
            ]
            self.points.append(point)
