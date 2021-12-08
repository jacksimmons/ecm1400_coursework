from covid_data_handler import covid_update_request
from covid_news_handling import news_API_request

import datetime

###Classes
class UpdateAction(enum.Enum):
    """An enum class to allow the representation of different actions by discrete integers."""
    COVID_UPDATE_REQUEST    = 0
    NEWS_UPDATE_REQUEST     = 1
    REPETITIVE_REQUEST      = 2
    TIMED_REQUEST           = 3

###Globals
#Mutable (-> global) objects
updates = []
news_articles = []
current_data = {"updates": updates, "news_articles": news_articles}

#Global (immutable) objects
name_error_counter = 0

###Utility functions
def get_date(offset:int=0) -> str:
    """Returns the date + the offset in YYYY-MM-DD (ISO 8601) format."""
    return (datetime.datetime.today() + datetime.timedelta(days=offset)).isoformat()

###Other functions
def do_updates() -> None:
    """Adds all of the updates in the global updates list to a scheduler, then runs that scheduler
    every time the scheduler's queue is empty. A never-ending procedure, so must be run in a separate
    thread to prevent the program from halting."""
    s = sched.scheduler(time.time, time.sleep)
    while True:
        if s.queue == []: #If the queue is empty, repopulate the queue.
            for update in updates:
                print(update["title"])
                for call in update["calls"]:
                    s.enter(update["interval"], 1, call)
                if not update["repetitive"]:
                    updates.remove(update) #If two identical updates exist, it doesn't matter which is removed.
            s.run()

def add_update(name:str, interval:float, actions:list=
               [UpdateAction.COVID_UPDATE_REQUEST,
                UpdateAction.REPETITIVE_REQUEST,
                UpdateAction.TIMED_REQUEST]) -> None:
    """Reformats and adds an update to the global updates list."""
    content = ""
    calls = []
    repetitive = False
    for action in actions: #Convert enum values to corresponding readable string values
        if action == UpdateAction.COVID_UPDATE_REQUEST:
            if content != "":
                content += ", "
            content += "Update Covid Data"
            calls.append(covid_update_request)
        elif action == UpdateAction.NEWS_UPDATE_REQUEST:
            if content != "":
                content += ", "
            content += "Update News Articles"
            calls.append(news_API_request)
        elif action == UpdateAction.REPETITIVE_REQUEST: #Sets the request to be repetitive
            if content != "":
                content += ", "
            content += "Repeating"
            repetitive = True
        elif action == UpdateAction.TIMED_REQUEST: #Sets the request to be timed. All requests are timed requests
            if content != "":
                content += ", "
            content += f"Interval (in seconds): {interval}"

    update = {"title":name, "interval": interval, "content":content, "calls":calls, "repetitive":repetitive}
    updates.append(update)
    #No need to refresh current_data["updates"] as updates is mutable.

def remove_update(name:str) -> None:
    """Removes an update by name lookup."""
    for update in updates:
        if update["title"] == name:
            updates.remove(update)
            break

def blacklist_article(name:str) -> None:
    """Removes and blacklists an article by name lookup."""
    for article in current_data["news_articles"]:
        if article["title"] == name:
            current_data["news_articles"].remove(article)
            with open("data/config.json", "r") as f:
                data = json.load(f)
            data["blacklisted_articles"].append(article["content"])
            with open("data/config.json", "w") as f:
                json.dump(obj=data, fp=f, indent=4)
            break

###FLASK
def create_app():
    """Creates and returns the Flask application."""
    app = Flask(__name__)
    app.debug = True
    return app
app = create_app()

@app.route("/")
def render_webpage():
    """Renders the root webpage."""
    global name_error_counter
    update_to_remove = request.args.get("update_item")
    article_to_remove = request.args.get("notif")

    if update_to_remove is not None:
        remove_update(update_to_remove)
        return redirect(request.path)

    if article_to_remove is not None:
        remove_article(article_to_remove)
        return redirect(request.path)            

    if name_error_counter >= 1:
        current_data.pop("name_err") #Error has already been displayed and the webpage has been updated since, so remove error.
        name_error_counter = 0

    if "name_err" in current_data:
        name_error_counter += 1

    return render_template(template_name_or_list="index.html", **current_data)

@app.route("/submit", methods=["POST"])
def submit_form():
    print(request.method)
    if request.method == "POST":
        update_covid_data = request.form.get("covid-data")
        update_news_articles = request.form.get("news")
        name = request.form["two"]

        if not (update_covid_data is None and update_news_articles is None): #If the update actually updates something
            if name not in (update["title"] for update in updates): #If the name provided is unique
                nice_interval = request.form["update"]
                interval = float(nice_interval[:2]) * 60 + float(nice_interval[3:]) #Convert "MM:SS" to seconds
                repeat_update = request.form.get("repeat")

                print(interval)

                content = []
                if update_covid_data is not None:
                    content.append(UpdateAction.COVID_UPDATE_REQUEST)
                if update_news_articles is not None:
                    content.append(UpdateAction.NEWS_UPDATE_REQUEST)
                if repeat_update is not None:
                    content.append(UpdateAction.REPETITIVE_REQUEST)
                content.append(UpdateAction.TIMED_REQUEST)

                add_update(name, interval, content) #also needs news update compatibility
            else:
                current_data["name_err"] = "Name already taken."
                name_error_counter = 0

    return redirect("/")

###Startup commands and global variable creation
add_update("update", 1, [UpdateAction.COVID_UPDATE_REQUEST])
update_runner = threading.Thread(None, do_updates) #Runs an infinite loop of executing updates asynchronously so the rest of the program runs in parallel.
update_runner.start()
###End of Startup

###Finalisation
if __name__ == "__main__":
    app.run()