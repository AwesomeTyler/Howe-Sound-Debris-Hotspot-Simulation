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

class AnimationManager:
    def __init__(self, ax, x_data, y_data, color='blue', lw=1):
        self.ax = ax
        self.x_data = x_data
        self.y_data = y_data
        self.line_collection = LineCollection(
            [], cmap='Blues', lw=lw, linestyle='solid', capstyle='round'
        )
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
        self.line_collection.set_segments(segments)

        # Check for intersections
        if len(segments) > 0:  # Ensure segments exist
            line_geom = gpd.GeoSeries([LineString(segments[-1])])  # Current segment as a LineString
            if self.parent.shapefile['geometry'].intersects(line_geom.iloc[0]).any():
                print("Intersection detected. Restarting animation.")
                self.line_collection.set_segments([])  # Clear the current line
                self.line_collection.set_alpha(1)  # Reset alpha to fully visible
                self.animation.event_source.stop()  # Stop the current animation
                self.start()  # Restart the animation
                return self.init()


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

        # Gradual fade-out for the entire line after 2 seconds (40 frames)
        if frame > 120:
            fade_out_factor = 1 - min(1, (frame - 120) / 100)  # Gradual fade out
            self.line_collection.set_alpha(fade_out_factor)

        # Reset animation when reaching the end of the data
        if frame >= len(self.x_data) - 1:
            frame = 0  # Reset frame to start the animation again
            self.line_collection.set_segments([])  # Clear the previous line
            self.line_collection.set_alpha(1)  # Reset alpha to fully visible

        return self.line_collection,

    def start(self, interval=10, total_frames=None):
        total_frames = total_frames or int(len(self.x_data))
        self.animation = FuncAnimation(
            self.ax.figure,
            self.animate,
            init_func=self.init,
            frames=total_frames,
            interval=interval,
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

    def start_multiple_animations(self, line_formula, start_coord, length=250):
        """
        Start animations based on a line formula and a starting coordinate.

        Parameters:
            line_formula (callable): A function that defines the line. It should take x as input and return y.
            start_coord (tuple): Starting coordinate of the line (x, y).
            length (int): Number of points to generate along the line.
        """
        x_start, y_start = start_coord

        # Generate x values dynamically
        x_values = np.linspace(x_start, x_start - 0.9, length)  # Extend x for `length` steps
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
        self.layout = self.findChild(QtWidgets.QVBoxLayout, 'verticalLayout')

        self.show()

    def plot_shapefile_in_layout(self):
        while self.layout.count():
            child = self.layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        if self.location_ComboBox.currentText() == "Northern Howe Sound":
            self.viewer = ShapefileViewer('Howe_Sound_Shapefile_Splited/Northern_Howe_Sound.shp')

        elif self.location_ComboBox.currentText() == "Central Howe Sound":
            self.viewer = ShapefileViewer('Howe_Sound_Shapefile_Splited/Central_Howe_Sound.shp')

        else:
            self.viewer = ShapefileViewer('Howe_Sound_Shapefile_Splited/Southern_Howe_Sound.shp')

        self.viewer.plot_shapefile()
        self.layout.addWidget(self.viewer.canvas)

        start_coord = (-10.5, -10.5)


        # Define line formula and starting coordinate
        def line_formula(x):
            return -(x-start_coord[0])*(x-start_coord[0]) + start_coord[1]
        def line_formula_2(x):
            return -2 * (x-start_coord[0])*(x-start_coord[0]) + start_coord[1]


        def line_formula_3(x):
            return -3 * (x-start_coord[0])*(x-start_coord[0]) + start_coord[1]

        #start_coord = (self.viewer.shapefile.total_bounds[2], self.viewer.shapefile.total_bounds[3])


        self.viewer.start_multiple_animations(line_formula, start_coord)
        #self.viewer.start_multiple_animations(line_formula_2, start_coord)
        #self.viewer.start_multiple_animations(line_formula_3, start_coord)




app = QtWidgets.QApplication(sys.argv)
window = Ui(path="Simulator.ui")
sys.exit(app.exec_())