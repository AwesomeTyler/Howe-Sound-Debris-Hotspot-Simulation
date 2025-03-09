import sys
import os
import geopandas as gpd
import matplotlib.pyplot as plt
from PyQt5 import uic, QtWidgets
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.animation import FuncAnimation
from matplotlib.collections import LineCollection
import numpy as np
from shapely.geometry import LineString
from PyQt5.QtWidgets import QLabel
from PyQt5.QtGui import QPixmap

class AnimationManager:
    def __init__(self, ax, x_data, y_data, color='blue', lw=1):
        self.ax = ax
        self.x_data = x_data
        self.y_data = y_data
        self.line_collection = LineCollection([], cmap='Blues', lw=lw, linestyle='solid', capstyle='round' )
        self.ax.add_collection(self.line_collection)
        self.animation = None

    def init(self):
        self.line_collection.set_segments([])
        self.line_collection.set_array(np.array([]))  # Reset alpha values
        return self.line_collection,

    def animate(self, frame):
        visible_length = 30  # Number of segments to display
        start_index = max(0, frame - visible_length)
        end_index = frame

        current_x = self.x_data[start_index:end_index]
        current_y = self.y_data[start_index:end_index]

        points = np.array([current_x, current_y]).T.reshape(-1, 1, 2)
        segments = np.concatenate([points[:-1], points[1:]], axis=1)

        if hasattr(self, 'frozen') and self.frozen:
            # Gradually fade the line if frozen
            current_alpha = self.line_collection.get_alpha()
            if current_alpha is None:  # Initialize alpha if not set
                current_alpha = 1.0
            alpha = current_alpha - 0.02  # Decrease alpha gradually
            if alpha <= 0:  # When fully faded, restart the animation
                self.line_collection.set_segments([])  # Clear the line
                self.line_collection.set_alpha(1)  # Reset alpha to fully visible
                self.frozen = False
                self.animation.event_source.stop()
                self.start()
            else:
                self.line_collection.set_alpha(alpha)
        else:
            self.line_collection.set_segments(segments)

            # Check for intersections
            if len(segments) > 0:  # Ensure segments exist
                line_geom = gpd.GeoSeries([LineString(segments[-1])])  # Current segment as a LineString
                if self.parent.shapefile['geometry'].intersects(line_geom.iloc[0]).any():
                    self.frozen = True
                    return self.line_collection,

            if len(current_x) > 1:
                # Create a gradient that fades to 0 at the tail
                distances = np.linspace(0, 1, len(current_x))  # Scale from 0 to 1
                alphas = np.exp(-((distances - 1) ** 2) * 10)  # Gaussian fade
                alphas[alphas < 0.01] = 0  # Force very small values to 0
                self.line_collection.set_array(alphas)

                # Gradually decrease line width
                max_linewidth = 1.5  # Maximum width at the head
                min_linewidth = 0.5  # Minimum width at the tail
                linewidths = np.linspace(min_linewidth, max_linewidth, len(current_x))
                self.line_collection.set_linewidths(linewidths)

        # Reset animation when reaching the end of the data
        if frame >= len(self.x_data) - 1:
            frame = 0  # Reset frame to start the animation again
            self.line_collection.set_segments([])  # Clear the previous line
            self.line_collection.set_alpha(1)  # Reset alpha to fully visible

        return self.line_collection,

    def start(self):
        total_frames = int(len(self.x_data))
        self.animation = FuncAnimation(
            self.ax.figure,
            self.animate,
            init_func=self.init,
            frames=total_frames,
            interval=10,
            blit=False
        )

class ShapefileViewer:
    def __init__(self, shapefile_path):
        self.shapefile_path = shapefile_path

        # Validate shapefile path
        if not os.path.exists(self.shapefile_path):
            print(f"Shapefile not found: {self.shapefile_path}")
            sys.exit(1)

        self.fig, self.ax = plt.subplots(figsize=(10, 10))
        self.canvas = FigureCanvas(self.fig)

        # Set up event handlers for zoom and drag
        self.dragging = False
        self.press_x = None
        self.press_y = None

        # Connect events
        self.cid_scroll = self.fig.canvas.mpl_connect('scroll_event', self.onScroll)
        self.cid_press = self.fig.canvas.mpl_connect('button_press_event', self.onPress)
        self.cid_release = self.fig.canvas.mpl_connect('button_release_event', self.onRelease)
        self.cid_move = self.fig.canvas.mpl_connect('motion_notify_event', self.onMove)

        self.red_dot = None
        self.animations = []  # To store multiple animation objects

    def plot_shapefile(self):

        self.shapefile = gpd.read_file(self.shapefile_path)
        self.shapefile['geometry'] = self.shapefile['geometry'].translate(xoff=-self.shapefile.total_bounds[2], yoff=-self.shapefile.total_bounds[3])
        self.shapefile['geometry'] = self.shapefile['geometry'].scale(xfact=-1 /self.shapefile.total_bounds[0], yfact=-1 /self.shapefile.total_bounds[0], origin=(0, 0))

        self.shapefile.plot(ax=self.ax, color='gray', edgecolor='black')
        self.ax.set_title('Howe Sound')
        self.ax.set_xlabel('Longitude')
        self.ax.set_ylabel('Latitude')
        self.canvas.draw()

    def onScroll(self, event):
        if event.button == 'up':
            self.zoom(event.xdata, event.ydata, 0.8)  # Zoom in
        elif event.button == 'down':
            self.zoom(event.xdata, event.ydata, 1.2)  # Zoom out

    def zoom(self, x, y, scale_factor):
        xlim = self.ax.get_xlim()
        ylim = self.ax.get_ylim()

        new_xlim = [x + (x_val - x) * scale_factor for x_val in xlim]
        new_ylim = [y + (y_val - y) * scale_factor for y_val in ylim]

        self.ax.set_xlim(new_xlim)
        self.ax.set_ylim(new_ylim)
        self.canvas.draw_idle()

    def onPress(self, event):
        if event.button == 1:  # Left mouse button
            self.dragging = True
            self.press_x = event.xdata
            self.press_y = event.ydata

        if event.dblclick:
            if event.xdata is not None and event.ydata is not None:
                self.plot_red_dot(event.xdata, event.ydata)

    def plot_red_dot(self, x, y):
        if self.red_dot:
            for dot in self.red_dot:
                dot.remove()

        self.red_dot = self.ax.plot(x, y, 'ro')  # Red dot
        print(x,y)
        self.fig.canvas.draw_idle()

    def onRelease(self, event):
        self.dragging = False
        self.press_x = None
        self.press_y = None

    def onMove(self, event):
        if self.dragging and event.xdata is not None and event.ydata is not None:
            dx = self.press_x - event.xdata
            dy = self.press_y - event.ydata

            xlim = self.ax.get_xlim()
            ylim = self.ax.get_ylim()

            self.ax.set_xlim([x + dx for x in xlim])
            self.ax.set_ylim([y + dy for y in ylim])

            self.press_x = event.xdata
            self.press_y = event.ydata

            self.canvas.draw_idle()

    def start_multiple_animations(self, line_formula, start_coord, length=250, speed=float, direction=None):
        """
        Start animations based on a line formula and a starting coordinate.

        Parameters:
            line_formula (callable): A function that defines the line. It should take x as input and return y.
            start_coord (tuple): Starting coordinate of the line (x, y).
            length (int): Number of points to generate along the line.
        """
        if direction == "RtoL":
            dir_factor = -1
        else:
            dir_factor = 1


        x_start, y_start = start_coord

        # Generate x values dynamically
        x_values = np.linspace(x_start, x_start + (dir_factor * speed), length)  # speed and direction here
        y_values = np.array([line_formula(x) for x in x_values])

        # Animation paths
        path = (x_values, y_values)

        # Start animation
        anim_manager = AnimationManager(self.ax, path[0], path[1], color='blue')
        anim_manager.parent = self  # Attach ShapefileViewer to AnimationManager
        anim_manager.start()
        self.animations.append(anim_manager)

        self.canvas.draw()


class Ui(QtWidgets.QMainWindow):
    def __init__(self, path):
        super(Ui, self).__init__()
        uic.loadUi(path, self)
        self.Start_Button = self.findChild(QtWidgets.QPushButton, 'Start_Button')
        self.Start_Button.clicked.connect(self.plot_shapefile_in_layout)
        self.location_ComboBox = self.findChild(QtWidgets.QComboBox, 'Combo_Box_Location')
        self.Season_ComboBox = self.findChild(QtWidgets.QComboBox, 'Combo_Box_Season')
        self.layout = self.findChild(QtWidgets.QVBoxLayout, 'verticalLayout')
        self.WindRose_layout = self.findChild(QtWidgets.QVBoxLayout, 'WindRose_Layout')
        self.WindRose_Daytime_Layout = self.findChild(QtWidgets.QVBoxLayout, 'WindRose_Daytime_Layout')
        self.WindRose_Label = self.findChild(QtWidgets.QLabel, 'Windrose_Label')
        self.WindRose_Daytime_Label = self.findChild(QtWidgets.QLabel, 'Windrose_Daytime_Label')

        self.show()


    def Add_Windrose(self, image_path=None, layout=None):
        image_label = QLabel()
        pixmap = QPixmap(image_path)
        image_label.setPixmap(pixmap)
        image_label.setScaledContents(True)

        # Clear previous widgets in WindRose_Layout
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        # Add image to layout
        layout.addWidget(image_label)


    # Summer in Northern Howe Sound
    def North_Fan_Line(self, x, Dir):
        return 0.5 * (Dir *(x+ 0.18) * (x + 0.18) -0.3) + 0.5 * ((x + 0.18) -0.3)

    def Central_Fan_Line(self, x, Dir, V_Offset):
        return 0.4 * (Dir * (x + 0.18) * (x + 0.18) ) + 0.2 * ((x + 0.18) - 0.3) - V_Offset
    def Central_Fan_Line2(self, x, Dir):
        return 0.4 * (Dir * (x + 0.18) * (x + 0.18) ) + 0.2 * ((x + 0.18) - 0.3) -0.22


    #Two most frequent daytime wind direction is 155 and 165
    def North_Summer(self,x,start_coor):
        return  -2.75 * (x - (start_coor[0])) + start_coor[1]


    # Winter in Northern Howe Sound
    #Two most frequent daytime wind direction is 335 and 355
    #Slope = tan(75) = 3.73
    def North_Winter(self,x,start_coor):
        return  -3.73 * (x - (start_coor[0])) + start_coor[1]


    #Summer in Central Howe Sound
    #Two most frequent daytime wind direction is 135 and 145
    #Slope = tan(50) = 1.19
    def central_summer_1(self,x, start_coor): #Wind Direction Flow
        return -1.19 * (x - (start_coor[0])) + start_coor[1]
    def central_summer_2(self,x, start_coor): #Upstream Flow
        return 1 * (x - (start_coor[0])) + start_coor[1]

    #Winter in Central Howe Sound
    #Two most frequent daytime wind direction is 345 and 355
    #Slope = tan(80) = 5.67
    def central_winter_1(self,x, start_coor): #Wind Direction Flow
        return -5.67 * (x - (start_coor[0])) + start_coor[1]




    #Summer in Southern Howe Sound, Two most frequent daytime wind direction is 275 and 285
    #Winter in Southern Howe Sound, Two most frequent daytime wind direction is 95 and 105
    #Both Slope = tan(10) = 0.176
    #Summer Westerlies, Winter Easterlies
    def Southern_Wind(self,x, start_coor): #Wind Direction Flow
        return -0.176 * (x - (start_coor[0])) + start_coor[1]





    def plot_shapefile_in_layout(self):
        while self.layout.count():
            child = self.layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        if self.location_ComboBox.currentText() == "Northern Howe Sound":

            self.viewer = ShapefileViewer('Howe_Sound_Shapefile_Splited/Northern_Howe_Sound.shp')

            if self.Season_ComboBox.currentText() == "Summer":
                self.Add_Windrose(image_path="Wind_Rose/North Summer.png",layout=self.WindRose_layout)
                self.WindRose_Label.setText("Northern Howe Sound Summer")
                self.Add_Windrose(image_path="Wind_Rose/North Summer Daytime.png",layout=self.WindRose_Daytime_Layout)
                self.WindRose_Daytime_Label.setText("Northern Howe Sound Summer Daytime")



                Fan_Shape_Factor = [10, 1.3, 0.6,-0.27]



                for i in Fan_Shape_Factor:
                    self.viewer.start_multiple_animations(lambda x: self.North_Fan_Line(x, i), (-0.18, -0.3), speed=0.8,
                                                          direction="RtoL")
                self.viewer.start_multiple_animations(lambda x: self.North_Summer(x, (-0.8, -1.6)), (-0.8, -1.6), speed=0.4,direction="RtoL")
                self.viewer.start_multiple_animations(lambda x: self.North_Summer(x, (-0.66, -1.46)), (-0.66, -1.46), speed=0.4,direction="RtoL")



            else:   #Northern Winter
                self.Add_Windrose(image_path="Wind_Rose/North Winter.png",layout=self.WindRose_layout)
                self.WindRose_Label.setText("Northern Howe Sound Winter")
                self.Add_Windrose(image_path="Wind_Rose/North Winter Daytime.png",layout=self.WindRose_Daytime_Layout)
                self.WindRose_Daytime_Label.setText("Northern Howe Sound Winter Daytime")
                Starting_Coord_Northern_Winter = [(-0.238, -0.3), (-0.44, -0.35), (-0.565, -0.43),(-0.73, -1.18), (-0.62, -0.95), (-0.544, -0.91)]

                for i in Starting_Coord_Northern_Winter:
                    self.viewer.start_multiple_animations(lambda x: self.North_Winter(x, i), i, speed=0.15, direction="LtoR")


        elif self.location_ComboBox.currentText() == "Central Howe Sound":
            self.viewer = ShapefileViewer('Howe_Sound_Shapefile_Splited/Central_Howe_Sound.shp')

            if self.Season_ComboBox.currentText() == "Summer":
                self.Add_Windrose(image_path="Wind_Rose/Central Summer.png",layout=self.WindRose_layout)
                self.WindRose_Label.setText("Central Howe Sound Summer")
                self.Add_Windrose(image_path="Wind_Rose/Central Summer Daytime.png",layout=self.WindRose_Daytime_Layout)
                self.WindRose_Daytime_Label.setText("Central Howe Sound Summer Daytime")

                Starting_Coord_Central_Summer = [(-0.45, -0.31), (-0.178, -0.5) ,(-0.21, -0.7), (-0.124, -0.49), (-0.31, -0.65), (-0.292, -0.94), (-0.35, -1),
                                                 (-0.67, -0.955), (-0.56, -0.91), (-0.54, -0.86), (-0.064, -1.04), (-0.855, -0.69), (-0.85, -0.54), (-0.598, -0.31), (-0.785, -0.797),
                                                 (-0.04, -0.9), (-0.07, -0.74)]

                for i in Starting_Coord_Central_Summer:
                    self.viewer.start_multiple_animations(lambda x: self.central_summer_1(x, i), i, speed=0.4, direction="RtoL")
                self.viewer.start_multiple_animations(lambda x: self.central_summer_2(x, (-0.16,-0.24)),(-0.16,-0.24), speed=0.3, direction= "RtoL")
                self.viewer.start_multiple_animations(lambda x: self.central_summer_2(x, (-0.11,-0.26)),(-0.11,-0.26), speed=0.3, direction= "RtoL")

                self.viewer.start_multiple_animations(lambda x: self.Central_Fan_Line(x, 14, V_Offset=0), (-0.07, 0.037), speed=0.35,direction="RtoL")
                self.viewer.start_multiple_animations(lambda x: self.Central_Fan_Line(x, 14, V_Offset=0.245), (-0.07, 0.037), speed=0.35,direction="RtoL")
                self.viewer.start_multiple_animations(lambda x: self.Central_Fan_Line(x, 14, V_Offset=0.292), (-0.07, 0.037), speed=0.35,direction="RtoL")
                self.viewer.start_multiple_animations(lambda x: self.Central_Fan_Line(x, 14, V_Offset=0.14), (-0.07, 0.037), speed=0.35,direction="RtoL")



            else: #Central Winter
                self.Add_Windrose(image_path="Wind_Rose/Central Winter.png",layout=self.WindRose_layout)
                self.WindRose_Label.setText("Central Howe Sound Winter")
                self.Add_Windrose(image_path="Wind_Rose/Central Winter Daytime.png",layout=self.WindRose_Daytime_Layout)
                self.WindRose_Daytime_Label.setText("Central Howe Sound Winter Daytime")
                Starting_Coord_Central_Winter = [(-0.035, -0.002), (-0.0853, -0.482), (-0.046, -0.68), (-0.074, -0.977), (-0.45, -0.9), (-0.74, -0.94),
                                                 (-0.689, -0.78), (-0.609, -0.776), (-0.2, -0.71), (-0.905, -0.334), (-0.422, -0.32), (-0.86, -0.49), (-0.83, -0.72)]
                for i in Starting_Coord_Central_Winter:
                    self.viewer.start_multiple_animations(lambda x: self.central_winter_1(x, i), i, speed=0.1, direction="LtoR")
                self.viewer.start_multiple_animations(lambda x: self.central_summer_2(x, (-0.16, -0.24)),(-0.16, -0.24), speed=0.3, direction="RtoL")
                self.viewer.start_multiple_animations(lambda x: self.central_summer_2(x, (-0.11, -0.26)),(-0.11, -0.26), speed=0.3, direction="RtoL")



        else:
            self.viewer = ShapefileViewer('Howe_Sound_Shapefile_Splited/Southern_Howe_Sound.shp')

            if self.Season_ComboBox.currentText() == "Summer":
                self.Add_Windrose(image_path="Wind_Rose/South Summer.png", layout=self.WindRose_layout)
                self.WindRose_Label.setText("South Howe Sound Summer")
                self.Add_Windrose(image_path="Wind_Rose/South Summer Daytime.png",layout=self.WindRose_Daytime_Layout)
                self.WindRose_Daytime_Label.setText("South Howe Sound Summer Daytime")
                Starting_Coord_South_Summer = [(-0.85, -0.186),(-0.82, -0.12),(-0.67, -0.355) , (-0.268, -0.392), (-0.24, -0.225), (-0.66, -0.093)]
                for i in Starting_Coord_South_Summer:
                    self.viewer.start_multiple_animations(lambda x: self.Southern_Wind(x, i), i, speed=0.3, direction="LtoR")

            else:
                self.Add_Windrose(image_path="Wind_Rose/South Winter.png", layout=self.WindRose_layout)
                self.WindRose_Label.setText("South Howe Sound Winter")
                self.Add_Windrose(image_path="Wind_Rose/South Winter Daytime.png",layout=self.WindRose_Daytime_Layout)
                self.WindRose_Daytime_Label.setText("South Howe Sound Winter Daytime")
                Starting_Coord_South_Winter = [(-0.05, -0.145),(-0.145, -0.277) , (-0.178, -0.468), (-0.56, -0.372), (-0.43, -0.124) , (-0.719, -0.328)]
                for i in Starting_Coord_South_Winter:
                    self.viewer.start_multiple_animations(lambda x: self.Southern_Wind(x, i), i, speed=0.3,direction="RtoL")

        self.viewer.plot_shapefile()
        self.layout.addWidget(self.viewer.canvas)








app = QtWidgets.QApplication(sys.argv)
window = Ui(path="Simulator.ui")
sys.exit(app.exec_())